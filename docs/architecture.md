# OmniRAG Architecture

## Overview

OmniRAG implements a multimodal RAG pipeline: ingest any document type, chunk it, embed it, store it in a vector database, and retrieve it using hybrid search with AI-generated, cited answers.

## Ingestion Pipeline

```
Input File
    → Format Detection
    → Ingester (PDF/Image/Code/Audio/Video)
    → Text Extraction
    → Chunker (smart, overlap-aware)
    → Embedder (OpenAI text-embedding-3-small)
    → ChromaDB Storage
    → BM25 Index Update
```

## Retrieval Pipeline

```
User Query
    → Query Embedding
    → Dense Search (ChromaDB cosine similarity)
    → Sparse Search (BM25 keyword)
    → RRF Fusion (Reciprocal Rank Fusion)
    → Top-K Reranking
    → LLM with context + citation instructions
    → Answer with [Source: doc, page N] citations
```

## Ingester Types

| Ingester | Library | Output |
|----------|---------|--------|
| PDF | PyMuPDF | Text + metadata per page |
| Image | pytesseract + OpenAI Vision | OCR text + description |
| Code | AST parsing | Code chunks by function/class |
| Audio | openai-whisper | Transcript with timestamps |
| Video | ffmpeg + whisper | Transcript + frame descriptions |

## Vector Store

ChromaDB with persistent storage:
- Collection per document type
- Metadata: source, page, chunk_index, timestamp
- Cosine similarity search

## Memory Layer

Conversation memory stored in Redis (session) + PostgreSQL (persistent):
- Multi-turn context window management
- Automatic summarization when context exceeds limit

## Knowledge Graph

Optional graph construction linking:
- Documents → Entities → Concepts
- Enables graph-based retrieval paths
