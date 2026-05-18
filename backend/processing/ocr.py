"""OCR processing with pytesseract and optional OpenAI Vision fallback."""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("omnirag.ocr")


class OCRProcessor:
    """Extract text from images via pytesseract (local) or OpenAI Vision."""

    def __init__(self, openai_client=None) -> None:
        self._openai_client = openai_client
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            logger.warning("pytesseract / Tesseract binary not available.")
            return False

    def extract_text(self, image_path: Path) -> str:
        """Extract text from an image file."""
        if self._tesseract_available:
            return self._tesseract_ocr(image_path)
        if self._openai_client:
            return self._vision_ocr(image_path)
        logger.error("No OCR backend available.")
        return ""

    def extract_text_from_bytes(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Extract text from raw image bytes."""
        if self._tesseract_available:
            return self._tesseract_ocr_bytes(image_bytes)
        if self._openai_client:
            return self._vision_ocr_bytes(image_bytes, mime_type)
        return ""

    def _tesseract_ocr(self, image_path: Path) -> str:
        import pytesseract
        from PIL import Image
        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img).strip()

    def _tesseract_ocr_bytes(self, image_bytes: bytes) -> str:
        import pytesseract
        from PIL import Image
        with Image.open(io.BytesIO(image_bytes)) as img:
            return pytesseract.image_to_string(img).strip()

    def _vision_ocr(self, image_path: Path) -> str:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        ext = image_path.suffix.lower().lstrip(".")
        mime_type = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "gif", "webp") else "image/png"
        return self._vision_ocr_bytes(image_bytes, mime_type)

    def _vision_ocr_bytes(self, image_bytes: bytes, mime_type: str) -> str:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = self._openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Please extract all text visible in this image. "
                                "Preserve layout as much as possible. "
                                "If there is no text, describe the image content."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    def describe_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Generate a natural language description of image content."""
        if not self._openai_client:
            return self.extract_text_from_bytes(image_bytes, mime_type)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = self._openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": "Describe this image in detail, including any diagrams, charts, figures, or text.",
                        },
                    ],
                }
            ],
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""
