"""Video ingestion with transcript extraction via Whisper or caption files."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.processing.chunker import SmartChunker
from backend.shared.models import Chunk, DocumentRecord, DocumentType

logger = logging.getLogger("omnirag.ingestion.video")

SUPPORTED_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".flv"}


class VideoIngester:
    """Extract transcripts from video files and index as text chunks."""

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
        """Ingest a video file by extracting its audio and transcribing."""
        fname = filename or file_path.name
        doc_id = str(uuid4())

        if file_path.suffix.lower() not in SUPPORTED_VIDEO:
            raise ValueError(f"Unsupported video format: {file_path.suffix}")

        transcript, duration_secs = self._transcribe(file_path)
        if not transcript:
            logger.warning(f"No transcript obtained for '{fname}'.")
            transcript = f"[Video: {fname} — transcript unavailable]"

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
            doc_type=DocumentType.VIDEO,
            file_size=file_path.stat().st_size if file_path.exists() else 0,
            chunk_count=len(chunks),
            metadata={"duration_seconds": duration_secs, "transcript_length": len(transcript)},
        )
        logger.info(f"Video '{fname}' ingested: {len(chunks)} chunks.")
        return record, chunks

    def _transcribe(self, video_path: Path) -> tuple[str, float]:
        """Extract audio and transcribe to text. Returns (transcript, duration)."""
        audio_path = self._extract_audio(video_path)
        if audio_path is None:
            return "", 0.0

        try:
            if self._openai_client:
                return self._openai_transcribe(audio_path)
            return self._local_whisper_transcribe(audio_path)
        finally:
            if audio_path.exists():
                audio_path.unlink(missing_ok=True)

    def _extract_audio(self, video_path: Path) -> Optional[Path]:
        """Extract audio track from video using ffmpeg or moviepy."""
        try:
            import subprocess
            audio_out = Path(tempfile.mktemp(suffix=".mp3"))
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "mp3", str(audio_out)],
                capture_output=True,
                timeout=300,
            )
            if result.returncode == 0 and audio_out.exists():
                return audio_out
        except FileNotFoundError:
            logger.warning("ffmpeg not found; trying moviepy.")
        except Exception as e:
            logger.warning(f"ffmpeg failed: {e}")

        try:
            from moviepy.editor import VideoFileClip
            audio_out = Path(tempfile.mktemp(suffix=".mp3"))
            with VideoFileClip(str(video_path)) as clip:
                if clip.audio:
                    clip.audio.write_audiofile(str(audio_out), logger=None)
                    return audio_out
        except ImportError:
            logger.warning("moviepy not installed.")
        except Exception as e:
            logger.warning(f"moviepy failed: {e}")

        return None

    def _openai_transcribe(self, audio_path: Path) -> tuple[str, float]:
        with open(audio_path, "rb") as f:
            response = self._openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
            )
        transcript = response.text or ""
        duration = getattr(response, "duration", 0.0) or 0.0
        return transcript, float(duration)

    def _local_whisper_transcribe(self, audio_path: Path) -> tuple[str, float]:
        try:
            import whisper
            model = whisper.load_model(self._whisper_model)
            result = model.transcribe(str(audio_path))
            return result.get("text", ""), result.get("segments", [{}])[-1].get("end", 0.0)
        except ImportError:
            logger.error("whisper package not installed. Install: pip install openai-whisper")
            return "", 0.0
