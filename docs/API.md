# OmniRAG API Reference

Base URL: `http://localhost:8000`

## Health

### GET /health
```json
{"status": "ok", "service": "OmniRAG"}
```

## Ingestion

### POST /api/v1/ingest/pdf
Upload and index a PDF file.

**Request:** `multipart/form-data` with field `file`

**Response:**
```json
{
  "document_id": "uuid",
  "pages": 42,
  "chunks": 186,
  "status": "indexed"
}
```

### POST /api/v1/ingest/image
Upload an image for OCR and vision understanding.

### POST /api/v1/ingest/code
```json
{"repo_path": "/path/to/repo", "language": "python"}
```

### POST /api/v1/ingest/url
```json
{"url": "https://example.com/article"}
```

## Search

### POST /api/v1/search/semantic
```json
{
  "query": "what is the authentication flow?",
  "top_k": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "...",
      "source": "architecture.pdf",
      "page": 5,
      "score": 0.92
    }
  ]
}
```

### POST /api/v1/search/hybrid
BM25 + dense vector search with RRF fusion.

## Query (RAG)

### POST /api/v1/query
Full RAG query with LLM and citations.

**Request:**
```json
{
  "question": "How does the payment system work?",
  "conversation_id": "optional-session-id"
}
```

**Response:**
```json
{
  "answer": "The payment system works by... [Source: payments.pdf, p.3]",
  "citations": [{"source": "payments.pdf", "page": 3, "excerpt": "..."}],
  "conversation_id": "uuid"
}
```

## Documents

### GET /api/v1/documents
List all indexed documents.

### DELETE /api/v1/documents/{doc_id}
Remove a document from the index.

## WebSocket

### WS /ws/chat
Streaming chat with documents.
