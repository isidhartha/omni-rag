"""Audio ingestion with Whisper transcription (local or OpenAI API)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.processing.chunker import SmartChunker
from backend.shared.models import Chunk, DocumentRecord, DocumentType

logger = logging.getLogger("omnirag.ingestion.audio")

SUPPORTED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".opus"}


class AudioIngester:
    """Transcribe audio files and index transcripts as searchable chunks."""

    def __init__(
        self,
        chunker: Optional[SmartChunker] = None,
        openai_client=None,
        whisper_model: str = "base",
    ) -> None:
        self._chunker = chunker or SmartChunker()
        self._openai_client = openai_client
        self._whisper_model = whisper_model

    def ingest(self, file_path: Path, filename: Optional[str] = None) -> tuple[DocumentRecord, list[Chunk]]:
        """Ingest an audio file by transcribing it."""
        fname = filename or file_path.name
        doc_id = str(uuid4())

        if file_path.suffix.lower() not in SUPPORTED_AUDIO:
            raise ValueError(f"Unsupported audio format: {file_path.suffix}")

        transcript, duration_secs, segments = self._transcribe(file_path)
        if not transcript:
            logger.warning(f"No transcript obtained for '{fname}'.")
            transcript = f"[Audio: {fname} — transcript unavailable]"

        chunks = self._chunker.chunk_text(
            text=transcript,
            doc_id=doc_id,
            source=fname,
        )
        for idx, chunk in enumerate(chunks):
            chunk.metadata.chunk_index = idx

        record = DocumentRecord(
            id=doc_id,
            filename=fname,
            doc_type=DocumentType.AUDIO,
            file_size=file_path.stat().st_size if file_path.exists() else 0,
            chunk_count=len(chunks),
            metadata={
                "duration_seconds": duration_secs,
                "segment_count": len(segments),
                "transcript_length": len(transcript),
            },
        )
        logger.info(f"Audio '{fname}' ingested: {len(chunks)} chunks (duration: {duration_secs:.1f}s).")
        return record, chunks

    def ingest_bytes(self, content: bytes, filename: str) -> tuple[DocumentRecord, list[Chunk]]:
        """Ingest audio from raw bytes via a temp file."""
        import tempfile
        suffix = Path(filename).suffix or ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            return self.ingest(tmp_path, filename)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _transcribe(self, audio_path: Path) -> tuple[str, float, list]:
        """Transcribe audio. Returns (text, duration_seconds, segments)."""
        if self._openai_client:
            return self._openai_transcribe(audio_path)
        return self._local_whisper_transcribe(audio_path)

    def _openai_transcribe(self, audio_path: Path) -> tuple[str, float, list]:
        with open(audio_path, "rb") as f:
            response = self._openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
            )
        transcript = response.text or ""
        duration = float(getattr(response, "duration", 0.0) or 0.0)
        segments = getattr(response, "segments", []) or []
        return transcript, duration, segments

    def _local_whisper_transcribe(self, audio_path: Path) -> tuple[str, float, list]:
        try:
            import whisper
            model = whisper.load_model(self._whisper_model)
            result = model.transcribe(str(audio_path))
            segments = result.get("segments", [])
            duration = segments[-1].get("end", 0.0) if segments else 0.0
            return result.get("text", ""), float(duration), segments
        except ImportError:
            logger.error("whisper package not installed. Install: pip install openai-whisper")
            return "", 0.0, []
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return "", 0.0, []
