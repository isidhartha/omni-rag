"""PDF ingestion using PyMuPDF with chunking and metadata extraction."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.processing.chunker import SmartChunker
from backend.shared.models import Chunk, DocumentRecord, DocumentType, IngestResponse

logger = logging.getLogger("omnirag.ingestion.pdf")


class PDFIngester:
    """Parse PDF files into chunks with page-level metadata."""

    def __init__(self, chunker: Optional[SmartChunker] = None) -> None:
        self._chunker = chunker or SmartChunker()

    def ingest(self, file_path: Path, filename: Optional[str] = None) -> tuple[DocumentRecord, list[Chunk]]:
        """Ingest a PDF file, return document record and chunks."""
        fname = filename or file_path.name
        doc_id = str(uuid4())

        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF (fitz) not installed. Install with: pip install pymupdf")
            raise ImportError("PyMuPDF is required for PDF ingestion.")

        chunks: list[Chunk] = []
        metadata: dict = {}

        with fitz.open(str(file_path)) as pdf:
            metadata = {
                "page_count": len(pdf),
                "title": pdf.metadata.get("title", ""),
                "author": pdf.metadata.get("author", ""),
                "subject": pdf.metadata.get("subject", ""),
                "creator": pdf.metadata.get("creator", ""),
            }
            logger.info(f"Ingesting PDF: {fname} ({len(pdf)} pages)")

            for page_num, page in enumerate(pdf, start=1):
                page_text = page.get_text("text")
                if not page_text.strip():
                    continue

                page_chunks = self._chunker.chunk_text(
                    text=page_text,
                    doc_id=doc_id,
                    source=fname,
                    page_number=page_num,
                )
                chunks.extend(page_chunks)

        # Re-index chunk indices globally
        for idx, chunk in enumerate(chunks):
            chunk.metadata.chunk_index = idx

        record = DocumentRecord(
            id=doc_id,
            filename=fname,
            doc_type=DocumentType.PDF,
            file_size=file_path.stat().st_size if file_path.exists() else 0,
            chunk_count=len(chunks),
            metadata=metadata,
        )

        logger.info(f"PDF '{fname}' ingested: {len(chunks)} chunks from {metadata['page_count']} pages.")
        return record, chunks

    def ingest_bytes(self, content: bytes, filename: str) -> tuple[DocumentRecord, list[Chunk]]:
        """Ingest PDF from raw bytes."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            return self.ingest(tmp_path, filename)
        finally:
            tmp_path.unlink(missing_ok=True)
