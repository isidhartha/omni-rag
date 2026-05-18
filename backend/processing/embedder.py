"""OpenAI embeddings with batch processing and local fallback."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Optional

from backend.shared.config import get_settings

logger = logging.getLogger("omnirag.embedder")


class EmbedderCache:
    """Simple in-memory embedding cache keyed by content hash."""

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = {}

    def get(self, text: str) -> Optional[list[float]]:
        key = hashlib.sha256(text.encode()).hexdigest()
        return self._store.get(key)

    def set(self, text: str, embedding: list[float]) -> None:
        key = hashlib.sha256(text.encode()).hexdigest()
        self._store[key] = embedding

    def __len__(self) -> int:
        return len(self._store)


class Embedder:
    """Embed text chunks using OpenAI or local sentence-transformers as fallback."""

    BATCH_SIZE = 100

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache = EmbedderCache()
        self._openai_client = self._try_load_openai()
        self._local_model = None  # lazy-loaded

    def _try_load_openai(self):
        """Attempt to initialise OpenAI client."""
        if not self._settings.openai_api_key:
            logger.info("No OpenAI key found — will use local embeddings.")
            return None
        try:
            from openai import OpenAI
            return OpenAI(api_key=self._settings.openai_api_key)
        except ImportError:
            logger.warning("openai package not installed — falling back to local model.")
            return None

    def _load_local_model(self):
        """Lazy-load sentence-transformers model."""
        if self._local_model is not None:
            return self._local_model
        try:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded local embedding model: all-MiniLM-L6-v2")
        except ImportError:
            logger.error("sentence-transformers not installed and OpenAI unavailable.")
            raise RuntimeError("No embedding backend available.")
        return self._local_model

    def embed(self, text: str) -> list[float]:
        """Embed a single string, using cache."""
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        result = self.embed_batch([text])[0]
        self._cache.set(text, result)
        return result

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple strings, respecting batch size limits."""
        if not texts:
            return []

        results: list[list[float]] = [None] * len(texts)  # type: ignore[list-item]
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            embeddings = self._compute_embeddings(uncached_texts)
            for idx, embedding, text in zip(uncached_indices, embeddings, uncached_texts):
                results[idx] = embedding
                self._cache.set(text, embedding)

        return results

    def _compute_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Compute embeddings for texts not in cache."""
        if self._openai_client is not None:
            return self._openai_embed(texts)
        return self._local_embed(texts)

    def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed via OpenAI API."""
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            response = self._openai_client.embeddings.create(
                model=self._settings.embedding_model,
                input=batch,
            )
            batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
            all_embeddings.extend(batch_embeddings)
        return all_embeddings

    def _local_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed using local sentence-transformers model."""
        model = self._load_local_model()
        embeddings = model.encode(texts, batch_size=self.BATCH_SIZE, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]
