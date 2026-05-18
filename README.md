# OmniRAG — Multimodal RAG Knowledge Engine

> Ingest PDFs, images, codebases, audio, and video. Ask questions. Get cited answers.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

## Features

- [x] PDF ingestion with chunking and metadata extraction
- [x] Image understanding (OCR + vision AI)
- [x] Codebase indexing (AST-aware semantic search)
- [x] Video/audio transcript extraction
- [x] Enterprise hybrid search (BM25 + dense vectors)
- [x] Persistent conversation memory
- [x] Citations with source + page reference
- [x] Knowledge graph construction
- [x] Multi-turn chat with your documents

## RAG Pipeline

```mermaid
graph LR
    A[Document] --> B{Ingestion Router}
    B --> C[PDF Parser]
    B --> D[Image OCR]
    B --> E[Code AST Parser]
    B --> F[Audio Transcriber]
    C & D & E & F --> G[Chunker]
    G --> H[Embedder - OpenAI]
    H --> I[(ChromaDB Vector Store)]
    J[User Query] --> K[Hybrid Search]
    K --> I
    K --> L[BM25 Index]
    I & L --> M[Reranker]
    M --> N[LLM with Citations]
    N --> O[Answer + Sources]
```

## Supported File Types

| Type | Formats |
|------|---------|
| Documents | PDF, DOCX, TXT, MD |
| Images | PNG, JPG, WEBP, TIFF |
| Code | Python, JS, TS, Go, Java, C++ |
| Audio | MP3, WAV, M4A |
| Video | MP4, MOV, AVI |
| Web | URLs (scraped) |

## Quick Start

```bash
git clone https://github.com/yourusername/omni-rag
cd omni-rag
cp .env.example .env
docker-compose up --build
```

Open `http://localhost:3000`. Upload a PDF and start asking questions.

## License

MIT — see [LICENSE](LICENSE).
