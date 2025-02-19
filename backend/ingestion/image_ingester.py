"""Image ingestion with OCR + OpenAI Vision understanding."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.processing.chunker import SmartChunker
from backend.processing.ocr import OCRProcessor
from backend.shared.models import Chunk, DocumentRecord, DocumentType

logger = logging.getLogger("omnirag.ingestion.image")

SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


class ImageIngester:
    """Ingest images via OCR and/or Vision AI to extract textual content."""

    def __init__(
        self,
        ocr_processor: Optional[OCRProcessor] = None,
        chunker: Optional[SmartChunker] = None,
        openai_client=None,
    ) -> None:
        self._ocr = ocr_processor or OCRProcessor(openai_client=openai_client)
        self._chunker = chunker or SmartChunker()
        self._openai_client = openai_client

    def ingest(self, file_path: Path, filename: Optional[str] = None) -> tuple[DocumentRecord, list[Chunk]]:
        """Ingest an image file: OCR text + vision description."""
        fname = filename or file_path.name
        doc_id = str(uuid4())

        if file_path.suffix.lower() not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported image format: {file_path.suffix}")

        with open(file_path, "rb") as f:
            image_bytes = f.read()

        return self._process(image_bytes, fname, doc_id, file_path.stat().st_size)

    def ingest_bytes(self, content: bytes, filename: str, mime_type: str = "image/png") -> tuple[DocumentRecord, list[Chunk]]:
        """Ingest an image from raw bytes."""
        doc_id = str(uuid4())
        return self._process(content, filename, doc_id, len(content), mime_type)

    def _process(
        self,
        image_bytes: bytes,
        filename: str,
        doc_id: str,
        file_size: int,
        mime_type: str = "image/png",
    ) -> tuple[DocumentRecord, list[Chunk]]:
        parts: list[str] = []

        # 1. OCR pass
        ocr_text = self._ocr.extract_text_from_bytes(image_bytes, mime_type)
        if ocr_text:
            parts.append(f"[OCR Text]\n{ocr_text}")

        # 2. Vision description (if available)
        if self._openai_client:
            description = self._ocr.describe_image(image_bytes, mime_type)
            if description:
                parts.append(f"[Vision Description]\n{description}")

        full_text = "\n\n".join(parts) or f"[Image: {filename} — no extractable text]"

        chunks = self._chunker.chunk_text(
            text=full_text,
            doc_id=doc_id,
            source=filename,
        )

        # Re-index
        for idx, chunk in enumerate(chunks):
            chunk.metadata.chunk_index = idx

        record = DocumentRecord(
            id=doc_id,
            filename=filename,
            doc_type=DocumentType.IMAGE,
            file_size=file_size,
            chunk_count=len(chunks),
            metadata={"mime_type": mime_type, "has_ocr": bool(ocr_text)},
        )
        logger.info(f"Image '{filename}' ingested: {len(chunks)} chunks.")
        return record, chunks
