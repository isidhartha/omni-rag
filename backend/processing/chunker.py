"""Smart document chunker with overlap, respecting document structure."""
from __future__ import annotations

import re
from typing import Iterator, Optional

from backend.shared.config import get_settings
from backend.shared.models import Chunk, ChunkMetadata


class SmartChunker:
    """Chunker that respects sentence/paragraph boundaries with configurable overlap."""

    SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+")
    PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> None:
        cfg = get_settings()
        self.chunk_size = chunk_size or cfg.chunk_size
        self.chunk_overlap = chunk_overlap or cfg.chunk_overlap

    def chunk_text(
        self,
        text: str,
        doc_id: str,
        source: Optional[str] = None,
        page_number: Optional[int] = None,
    ) -> list[Chunk]:
        """Split text into overlapping chunks, respecting paragraph/sentence boundaries."""
        if not text or not text.strip():
            return []

        paragraphs = self.PARAGRAPH_SPLIT.split(text)
        raw_chunks = list(self._merge_paragraphs(paragraphs))

        chunks: list[Chunk] = []
        char_offset = 0
        for idx, chunk_text in enumerate(raw_chunks):
            meta = ChunkMetadata(
                doc_id=doc_id,
                chunk_index=idx,
                page_number=page_number,
                start_char=char_offset,
                end_char=char_offset + len(chunk_text),
                source=source,
            )
            chunks.append(Chunk(text=chunk_text.strip(), metadata=meta))
            char_offset += len(chunk_text) - self.chunk_overlap

        return chunks

    def _merge_paragraphs(self, paragraphs: list[str]) -> Iterator[str]:
        """Merge paragraphs into chunks of target size with overlap."""
        buffer = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(buffer) + len(para) + 1 <= self.chunk_size:
                buffer = (buffer + "\n\n" + para).strip() if buffer else para
            else:
                if buffer:
                    yield buffer
                    overlap_text = self._extract_overlap(buffer)
                    buffer = (overlap_text + "\n\n" + para).strip() if overlap_text else para
                else:
                    # Paragraph itself exceeds chunk size — split by sentence
                    yield from self._split_large_paragraph(para)
                    buffer = ""

        if buffer:
            yield buffer

    def _extract_overlap(self, text: str) -> str:
        """Extract trailing overlap from previous chunk."""
        if self.chunk_overlap <= 0:
            return ""
        return text[-self.chunk_overlap :] if len(text) >= self.chunk_overlap else text

    def _split_large_paragraph(self, text: str) -> Iterator[str]:
        """Split an oversized paragraph by sentences."""
        sentences = self.SENTENCE_ENDINGS.split(text)
        buffer = ""
        for sentence in sentences:
            if len(buffer) + len(sentence) + 1 <= self.chunk_size:
                buffer = (buffer + " " + sentence).strip() if buffer else sentence
            else:
                if buffer:
                    yield buffer
                    overlap = self._extract_overlap(buffer)
                    buffer = (overlap + " " + sentence).strip() if overlap else sentence
                else:
                    # Single sentence too long — hard split
                    for i in range(0, len(sentence), self.chunk_size - self.chunk_overlap):
                        yield sentence[i : i + self.chunk_size]
        if buffer:
            yield buffer

    def chunk_code(
        self,
        code: str,
        doc_id: str,
        language: str = "python",
        source: Optional[str] = None,
    ) -> list[Chunk]:
        """Chunk code by logical blocks (functions/classes) with line-aware splitting."""
        lines = code.splitlines(keepends=True)
        chunks: list[Chunk] = []
        buffer_lines: list[str] = []
        buffer_len = 0
        chunk_idx = 0

        for line in lines:
            line_len = len(line)
            if buffer_len + line_len > self.chunk_size and buffer_lines:
                chunk_text = "".join(buffer_lines).strip()
                if chunk_text:
                    meta = ChunkMetadata(
                        doc_id=doc_id,
                        chunk_index=chunk_idx,
                        source=source,
                        language=language,
                    )
                    chunks.append(Chunk(text=chunk_text, metadata=meta))
                    chunk_idx += 1
                # Keep overlap lines
                overlap_chars = 0
                new_buffer: list[str] = []
                for ol in reversed(buffer_lines):
                    if overlap_chars + len(ol) <= self.chunk_overlap:
                        new_buffer.insert(0, ol)
                        overlap_chars += len(ol)
                    else:
                        break
                buffer_lines = new_buffer
                buffer_len = sum(len(l) for l in buffer_lines)

            buffer_lines.append(line)
            buffer_len += line_len

        if buffer_lines:
            chunk_text = "".join(buffer_lines).strip()
            if chunk_text:
                meta = ChunkMetadata(
                    doc_id=doc_id,
                    chunk_index=chunk_idx,
                    source=source,
                    language=language,
                )
                chunks.append(Chunk(text=chunk_text, metadata=meta))

        return chunks
