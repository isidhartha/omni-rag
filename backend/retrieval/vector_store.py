"""ChromaDB-based vector store with CRUD operations."""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.shared.config import get_settings
from backend.shared.models import Chunk, DocumentRecord, DocumentType, SearchResult

logger = logging.getLogger("omnirag.retrieval.vector_store")


class VectorStore:
    """Persistent vector store backed by ChromaDB."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = None
        self._collection = None
        self._doc_registry: dict[str, DocumentRecord] = {}

    def _get_client(self):
        """Lazy-initialise ChromaDB client."""
        if self._client is not None:
            return self._client
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            chroma_host = self._settings.chroma_host
            chroma_port = self._settings.chroma_port

            # Try HTTP client first (for Docker), fallback to in-process
            try:
                self._client = chromadb.HttpClient(
                    host=chroma_host,
                    port=chroma_port,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._client.heartbeat()
                logger.info(f"Connected to ChromaDB at {chroma_host}:{chroma_port}")
            except Exception:
                logger.warning("ChromaDB HTTP client failed; using in-process ephemeral store.")
                self._client = chromadb.EphemeralClient(
                    settings=ChromaSettings(anonymized_telemetry=False)
                )

        except ImportError:
            logger.error("chromadb not installed. Install with: pip install chromadb")
            raise

        return self._client

    def _get_collection(self):
        """Lazy-initialise or get the ChromaDB collection."""
        if self._collection is not None:
            return self._collection
        client = self._get_client()
        self._collection = client.get_or_create_collection(
            name=self._settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    def add_chunks(self, chunks: list[Chunk], document_record: DocumentRecord) -> None:
        """Embed and store chunks in ChromaDB."""
        if not chunks:
            return

        collection = self._get_collection()
        self._doc_registry[document_record.id] = document_record

        ids = [chunk.id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "doc_id": chunk.metadata.doc_id,
                "chunk_index": chunk.metadata.chunk_index,
                "page_number": chunk.metadata.page_number or 0,
                "source": chunk.metadata.source or "",
                "section": chunk.metadata.section or "",
                "language": chunk.metadata.language or "",
                "filename": document_record.filename,
                "doc_type": document_record.doc_type.value,
                "start_char": chunk.metadata.start_char or 0,
                "end_char": chunk.metadata.end_char or 0,
            }
            for chunk in chunks
        ]
        embeddings = [chunk.embedding for chunk in chunks if chunk.embedding is not None]
        use_embeddings = len(embeddings) == len(chunks)

        if use_embeddings:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        else:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        logger.info(f"Stored {len(chunks)} chunks for doc '{document_record.filename}'.")

    def query(
        self,
        query_embedding: Optional[list[float]],
        query_text: str,
        top_k: int = 10,
        where: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """Query the vector store, returning ranked SearchResults."""
        collection = self._get_collection()

        kwargs: dict[str, Any] = {
            "n_results": min(top_k, collection.count() or 1),
            "include": ["documents", "metadatas", "distances"],
        }
        if query_embedding:
            kwargs["query_embeddings"] = [query_embedding]
        else:
            kwargs["query_texts"] = [query_text]
        if where:
            kwargs["where"] = where

        try:
            results = collection.query(**kwargs)
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []

        search_results: list[SearchResult] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for chunk_id, doc_text, meta, dist in zip(ids, docs, metas, distances):
            cosine_score = max(0.0, 1.0 - float(dist))
            doc_record = self._doc_registry.get(meta.get("doc_id", ""))
            from backend.shared.models import ChunkMetadata
            chunk_meta = ChunkMetadata(
                doc_id=meta.get("doc_id", ""),
                chunk_index=int(meta.get("chunk_index", 0)),
                page_number=int(meta.get("page_number")) if meta.get("page_number") else None,
                source=meta.get("source"),
                section=meta.get("section") or None,
                language=meta.get("language") or None,
                start_char=int(meta.get("start_char", 0)) or None,
                end_char=int(meta.get("end_char", 0)) or None,
            )
            search_results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    text=doc_text,
                    score=cosine_score,
                    doc_id=meta.get("doc_id", ""),
                    filename=meta.get("filename", "unknown"),
                    doc_type=DocumentType(meta.get("doc_type", "text")),
                    metadata=chunk_meta,
                )
            )

        return search_results

    def delete_document(self, doc_id: str) -> int:
        """Remove all chunks belonging to a document."""
        collection = self._get_collection()
        try:
            existing = collection.get(where={"doc_id": doc_id})
            ids_to_delete = existing.get("ids", [])
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
            self._doc_registry.pop(doc_id, None)
            logger.info(f"Deleted {len(ids_to_delete)} chunks for doc_id='{doc_id}'.")
            return len(ids_to_delete)
        except Exception as e:
            logger.error(f"Delete failed for doc_id={doc_id}: {e}")
            return 0

    def list_documents(self) -> list[DocumentRecord]:
        """Return all registered document records."""
        return list(self._doc_registry.values())

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        return self._doc_registry.get(doc_id)

    def count(self) -> int:
        return self._get_collection().count()
