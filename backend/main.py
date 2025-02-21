"""OmniRAG — Multimodal RAG Knowledge Engine.

FastAPI application entry point with all API routes.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from backend.shared.config import get_settings
from backend.shared.logging import configure_logging
from backend.llm_service import LLM_PROVIDER, chat as llm_chat
from backend.shared.models import (
    Citation,
    DocumentRecord,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SearchQuery,
    SearchResponse,
    SearchResult,
)

# --- Bootstrap logging ---
_settings = get_settings()
configure_logging(_settings.log_level)
logger = logging.getLogger("omnirag.main")

# ---------------------------------------------------------------------------
# Dependency singletons (initialised in lifespan)
# ---------------------------------------------------------------------------
_vector_store = None
_embedder = None
_hybrid_search = None
_semantic_search = None
_conversation_memory = None
_knowledge_graph = None
_summarizer = None
_pdf_ingester = None
_image_ingester = None
_code_ingester = None
_video_ingester = None
_audio_ingester = None
_openai_client = None
_anthropic_client = None


def _init_llm_clients():
    """Initialise LLM clients if API keys are present."""
    global _openai_client, _anthropic_client
    if _settings.openai_api_key:
        try:
            from openai import OpenAI
            _openai_client = OpenAI(api_key=_settings.openai_api_key)
            logger.info("OpenAI client initialised.")
        except ImportError:
            logger.warning("openai package not installed.")

    if _settings.anthropic_api_key:
        try:
            import anthropic
            _anthropic_client = anthropic.Anthropic(api_key=_settings.anthropic_api_key)
            logger.info("Anthropic client initialised.")
        except ImportError:
            logger.warning("anthropic package not installed.")


def _init_redis():
    """Attempt Redis connection, return None on failure."""
    try:
        import redis
        client = redis.from_url(_settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        logger.info("Redis connected.")
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}); using in-memory only.")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global (
        _vector_store, _embedder, _hybrid_search, _semantic_search,
        _conversation_memory, _knowledge_graph, _summarizer,
        _pdf_ingester, _image_ingester, _code_ingester,
        _video_ingester, _audio_ingester,
    )
    logger.info("OmniRAG starting up...")

    # Ensure upload directory exists
    Path(_settings.upload_dir).mkdir(parents=True, exist_ok=True)

    _init_llm_clients()
    redis_client = _init_redis()

    # Processing layer
    from backend.processing.chunker import SmartChunker
    from backend.processing.embedder import Embedder
    from backend.processing.ocr import OCRProcessor
    from backend.processing.summarizer import Summarizer

    chunker = SmartChunker()
    _embedder = Embedder()
    ocr = OCRProcessor(openai_client=_openai_client)
    _summarizer = Summarizer(openai_client=_openai_client, anthropic_client=_anthropic_client)

    # Storage layer
    from backend.retrieval.vector_store import VectorStore
    _vector_store = VectorStore()

    # Retrieval layer
    from backend.retrieval.hybrid_search import HybridSearch
    from backend.retrieval.semantic_search import SemanticSearch
    _hybrid_search = HybridSearch(vector_store=_vector_store, embedder=_embedder)
    _semantic_search = SemanticSearch(vector_store=_vector_store, embedder=_embedder)

    # Memory layer
    from backend.memory.conversation_memory import ConversationMemory
    from backend.memory.knowledge_graph import KnowledgeGraph
    _conversation_memory = ConversationMemory(redis_client=redis_client)
    _knowledge_graph = KnowledgeGraph()

    # Ingestion layer
    from backend.ingestion.pdf_ingester import PDFIngester
    from backend.ingestion.image_ingester import ImageIngester
    from backend.ingestion.code_ingester import CodeIngester
    from backend.ingestion.video_ingester import VideoIngester
    from backend.ingestion.audio_ingester import AudioIngester
    _pdf_ingester = PDFIngester(chunker=chunker)
    _image_ingester = ImageIngester(ocr_processor=ocr, chunker=chunker, openai_client=_openai_client)
    _code_ingester = CodeIngester()
    _video_ingester = VideoIngester(chunker=chunker, openai_client=_openai_client)
    _audio_ingester = AudioIngester(chunker=chunker, openai_client=_openai_client)

    logger.info("OmniRAG ready.")
    yield

    logger.info("OmniRAG shutting down.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="OmniRAG",
    description="Multimodal RAG Knowledge Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper: embed + store chunks
# ---------------------------------------------------------------------------
def _embed_and_store(record: DocumentRecord, chunks) -> None:
    """Compute embeddings for chunks and persist to vector store."""
    texts = [c.text for c in chunks]
    if texts:
        embeddings = _embedder.embed_batch(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb
    _vector_store.add_chunks(chunks, record)

    # Update BM25 index
    bm25_docs = [
        {
            "chunk_id": c.id,
            "text": c.text,
            "doc_id": c.metadata.doc_id,
            "filename": record.filename,
            "doc_type": record.doc_type.value,
            "chunk_index": c.metadata.chunk_index,
            "source": c.metadata.source,
            "page_number": c.metadata.page_number,
        }
        for c in chunks
    ]
    _hybrid_search.add_to_bm25_index(bm25_docs)

    # Register in knowledge graph
    entities = _extract_entities(record, chunks)
    _knowledge_graph.add_document(
        doc_id=record.id,
        entities=entities,
        metadata={
            "filename": record.filename,
            "doc_type": record.doc_type.value,
        },
    )


def _extract_entities(record: DocumentRecord, chunks) -> list[str]:
    """Naively extract potential entity tokens from metadata."""
    entities: list[str] = [record.filename]
    for chunk in chunks[:5]:
        words = chunk.text.split()
        # Keep capitalised words as candidate entities (simple heuristic)
        entities.extend(w.strip(".,;:") for w in words if w and w[0].isupper() and len(w) > 2)
    return list(set(entities))[:50]


def _build_citations(results: list[SearchResult]) -> list[Citation]:
    return [
        Citation(
            doc_id=r.doc_id,
            filename=r.filename,
            chunk_id=r.chunk_id,
            page_number=r.metadata.page_number,
            section=r.metadata.section,
            text_excerpt=r.text[:300],
            relevance_score=r.score,
        )
        for r in results
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "OmniRAG", "version": "1.0.0"}


@app.get("/api/v1/documents", response_model=list[DocumentRecord], tags=["documents"])
async def list_documents():
    """List all indexed documents."""
    return _vector_store.list_documents()


@app.delete("/api/v1/documents/{doc_id}", tags=["documents"])
async def delete_document(doc_id: str):
    """Delete a document and all its indexed chunks."""
    deleted_count = _vector_store.delete_document(doc_id)
    _knowledge_graph.remove_document(doc_id)
    if deleted_count == 0:
        # doc may not exist but that's fine — return 200 regardless
        return {"status": "not_found", "doc_id": doc_id, "chunks_removed": 0}
    return {"status": "deleted", "doc_id": doc_id, "chunks_removed": deleted_count}


# --- Ingestion ---

@app.post("/api/v1/ingest/pdf", response_model=IngestResponse, tags=["ingestion"])
async def ingest_pdf(file: UploadFile = File(...)):
    """Upload and ingest a PDF document."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a PDF.")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:  # 100 MB limit
        raise HTTPException(413, "PDF exceeds 100 MB limit.")

    try:
        record, chunks = _pdf_ingester.ingest_bytes(content, file.filename)
        _embed_and_store(record, chunks)
        return IngestResponse(
            doc_id=record.id,
            filename=record.filename,
            chunk_count=len(chunks),
            status="indexed",
            message=f"PDF ingested: {len(chunks)} chunks from {record.metadata.get('page_count', '?')} pages.",
        )
    except ImportError as e:
        raise HTTPException(503, f"Dependency missing: {e}")
    except Exception as e:
        logger.exception(f"PDF ingest failed: {e}")
        raise HTTPException(500, f"Ingestion failed: {e}")


@app.post("/api/v1/ingest/image", response_model=IngestResponse, tags=["ingestion"])
async def ingest_image(file: UploadFile = File(...)):
    """Upload and ingest an image (OCR + Vision AI)."""
    content = await file.read()
    mime_type = file.content_type or "image/png"
    filename = file.filename or f"image_{uuid4().hex[:8]}.png"

    try:
        record, chunks = _image_ingester.ingest_bytes(content, filename, mime_type)
        _embed_and_store(record, chunks)
        return IngestResponse(
            doc_id=record.id,
            filename=record.filename,
            chunk_count=len(chunks),
            status="indexed",
            message=f"Image ingested with {'OCR' if record.metadata.get('has_ocr') else 'vision'} extraction.",
        )
    except Exception as e:
        logger.exception(f"Image ingest failed: {e}")
        raise HTTPException(500, f"Ingestion failed: {e}")


@app.post("/api/v1/ingest/code", response_model=list[IngestResponse], tags=["ingestion"])
async def ingest_code(repo_path: str = Form(...)):
    """Index a local codebase by path."""
    path = Path(repo_path)
    if not path.exists():
        raise HTTPException(404, f"Path not found: {repo_path}")

    try:
        if path.is_file():
            pairs = [_code_ingester.ingest_file(path)]
        else:
            pairs = _code_ingester.ingest_directory(path)

        responses: list[IngestResponse] = []
        for record, chunks in pairs:
            _embed_and_store(record, chunks)
            responses.append(IngestResponse(
                doc_id=record.id,
                filename=record.filename,
                chunk_count=len(chunks),
                status="indexed",
                message=f"Code file indexed ({record.metadata.get('language', 'unknown')} language).",
            ))
        return responses
    except Exception as e:
        logger.exception(f"Code ingest failed: {e}")
        raise HTTPException(500, f"Ingestion failed: {e}")


@app.post("/api/v1/ingest/url", response_model=IngestResponse, tags=["ingestion"])
async def ingest_url(url: str = Form(...)):
    """Scrape and index web content from a URL."""
    try:
        content, title = await _scrape_url(url)
        if not content:
            raise HTTPException(422, "Could not extract content from URL.")

        from backend.processing.chunker import SmartChunker
        from backend.shared.models import DocumentRecord, DocumentType

        doc_id = str(uuid4())
        chunker = SmartChunker()
        chunks = chunker.chunk_text(text=content, doc_id=doc_id, source=url)
        for idx, chunk in enumerate(chunks):
            chunk.metadata.chunk_index = idx

        record = DocumentRecord(
            id=doc_id,
            filename=title or url,
            doc_type=DocumentType.URL,
            file_size=len(content.encode()),
            chunk_count=len(chunks),
            metadata={"url": url, "title": title},
        )
        _embed_and_store(record, chunks)
        return IngestResponse(
            doc_id=doc_id,
            filename=title or url,
            chunk_count=len(chunks),
            status="indexed",
            message=f"URL scraped and indexed: {len(chunks)} chunks.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"URL ingest failed: {e}")
        raise HTTPException(500, f"Ingestion failed: {e}")


async def _scrape_url(url: str) -> tuple[str, str]:
    """Scrape URL content using httpx + html2text."""
    try:
        import httpx, html2text
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "OmniRAG/1.0"})
            response.raise_for_status()

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        text = h.handle(response.text)

        # Extract title
        import re
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", response.text, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else url

        return text, title
    except ImportError:
        logger.warning("httpx or html2text not installed; trying basic urllib.")
        import urllib.request
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        import re
        text = re.sub(r"<[^>]+>", " ", raw)
        return text, url


# --- Search ---

@app.post("/api/v1/search/semantic", response_model=SearchResponse, tags=["search"])
async def semantic_search(query: SearchQuery):
    """Semantic vector search across all indexed documents."""
    start = time.perf_counter()
    doc_types = [dt.value for dt in query.doc_types] if query.doc_types else None
    results = _semantic_search.search(
        query=query.query,
        top_k=query.top_k,
        rerank=True,
        doc_ids=query.doc_ids,
        doc_types=doc_types,
    )
    filtered = [r for r in results if r.score >= query.min_score]
    elapsed = (time.perf_counter() - start) * 1000
    return SearchResponse(query=query.query, results=filtered, total=len(filtered), elapsed_ms=elapsed)


@app.post("/api/v1/search/hybrid", response_model=SearchResponse, tags=["search"])
async def hybrid_search(query: SearchQuery):
    """Hybrid dense + sparse search with Reciprocal Rank Fusion."""
    start = time.perf_counter()
    doc_types = [dt.value for dt in query.doc_types] if query.doc_types else None
    where = _semantic_search._build_where(query.doc_ids, doc_types)
    results = _hybrid_search.search(query=query.query, top_k=query.top_k, where=where)
    filtered = [r for r in results if r.score >= query.min_score]
    elapsed = (time.perf_counter() - start) * 1000
    return SearchResponse(query=query.query, results=filtered, total=len(filtered), elapsed_ms=elapsed)


# --- RAG Query ---

@app.post("/api/v1/query", response_model=QueryResponse, tags=["rag"])
async def rag_query(request: QueryRequest):
    """RAG query: retrieve + generate answer with source citations."""
    start = time.perf_counter()

    # Retrieve relevant chunks
    doc_types = None
    where = _semantic_search._build_where(request.doc_ids, doc_types)
    results = _hybrid_search.search(query=request.question, top_k=request.top_k, where=where)

    # Build or fetch conversation
    conv_id = request.conversation_id
    if conv_id:
        _conversation_memory.add_message(conv_id, "user", request.question)
    else:
        ctx = _conversation_memory.create_conversation(doc_ids=request.doc_ids or [])
        conv_id = ctx.conversation_id
        _conversation_memory.add_message(conv_id, "user", request.question)

    # Generate answer
    context_chunks = [
        {
            "chunk_id": r.chunk_id,
            "text": r.text,
            "filename": r.filename,
            "doc_id": r.doc_id,
        }
        for r in results
    ]
    answer = _summarizer.answer_with_context(
        question=request.question,
        context_chunks=context_chunks,
    )

    _conversation_memory.add_message(conv_id, "assistant", answer)

    citations = _build_citations(results)
    elapsed = (time.perf_counter() - start) * 1000

    return QueryResponse(
        answer=answer,
        citations=citations,
        conversation_id=conv_id,
        elapsed_ms=elapsed,
    )


# --- WebSocket Chat ---

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Streaming WebSocket chat with documents."""
    await websocket.accept()
    conversation_id: Optional[str] = None

    try:
        while True:
            data = await websocket.receive_json()
            question = data.get("question", "").strip()
            doc_ids = data.get("doc_ids")

            if not question:
                await websocket.send_json({"type": "error", "message": "Empty question."})
                continue

            if not conversation_id:
                ctx = _conversation_memory.create_conversation(doc_ids=doc_ids or [])
                conversation_id = ctx.conversation_id

            await websocket.send_json({"type": "status", "message": "Retrieving context..."})

            where = _semantic_search._build_where(doc_ids, None)
            results = _hybrid_search.search(query=question, top_k=5, where=where)

            _conversation_memory.add_message(conversation_id, "user", question)

            context_chunks = [
                {"chunk_id": r.chunk_id, "text": r.text, "filename": r.filename, "doc_id": r.doc_id}
                for r in results
            ]

            # Stream answer token by token if OpenAI available; fall back to llm_service
            if LLM_PROVIDER == "ollama":
                answer = _summarizer.answer_with_context(
                    question=question, context_chunks=context_chunks
                )
                await websocket.send_json({"type": "answer_chunk", "content": answer})
            elif _openai_client:
                answer = await _stream_openai_response(
                    websocket, question, context_chunks, conversation_id
                )
            else:
                answer = _summarizer.answer_with_context(
                    question=question, context_chunks=context_chunks
                )
                await websocket.send_json({"type": "answer_chunk", "content": answer})

            _conversation_memory.add_message(conversation_id, "assistant", answer)
            citations = _build_citations(results)

            await websocket.send_json({
                "type": "done",
                "conversation_id": conversation_id,
                "citations": [c.model_dump() for c in citations],
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected (conv={conversation_id})")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


async def _stream_openai_response(
    websocket: WebSocket,
    question: str,
    context_chunks: list[dict],
    conversation_id: str,
) -> str:
    """Stream OpenAI chat completion over WebSocket."""
    from backend.processing.summarizer import Summarizer

    context_parts = [
        f"[Source: {c['filename']}]\n{c['text']}" for c in context_chunks
    ]
    context = "\n\n---\n\n".join(context_parts)
    messages = _conversation_memory.get_context_window(conversation_id)[:-1]  # exclude latest user msg
    messages.append({
        "role": "user",
        "content": (
            f"Answer based on this context:\n\n{context[:6000]}\n\n"
            f"Question: {question}"
        ),
    })

    full_answer = ""
    stream = _openai_client.chat.completions.create(
        model=_settings.llm_model,
        messages=messages,
        max_tokens=1024,
        temperature=0.2,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            full_answer += delta
            await websocket.send_json({"type": "answer_chunk", "content": delta})

    return full_answer


# --- Knowledge Graph endpoint ---

@app.get("/api/v1/graph/{doc_id}", tags=["knowledge-graph"])
async def get_knowledge_graph(doc_id: str):
    """Return the knowledge graph subgraph centred on a document."""
    return _knowledge_graph.get_entity_graph(doc_id)


@app.get("/api/v1/graph/stats", tags=["knowledge-graph"])
async def get_graph_stats():
    """Return overall knowledge graph statistics."""
    return _knowledge_graph.stats()
