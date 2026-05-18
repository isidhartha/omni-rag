"""Semantic search pipeline with cross-encoder re-ranking."""
from __future__ import annotations

import logging
from typing import Optional

from backend.shared.models import SearchResult

logger = logging.getLogger("omnirag.retrieval.semantic")


class SemanticSearch:
    """Dense vector search with optional cross-encoder re-ranking."""

    def __init__(self, vector_store, embedder) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._reranker = None

    def _load_reranker(self):
        """Lazy-load cross-encoder re-ranker."""
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder
            self._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.info("Loaded cross-encoder re-ranker.")
        except ImportError:
            logger.warning("sentence-transformers not installed; skipping re-ranking.")
        return self._reranker

    def search(
        self,
        query: str,
        top_k: int = 10,
        rerank: bool = True,
        doc_ids: Optional[list[str]] = None,
        doc_types: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """Run semantic search with optional re-ranking."""
        fetch_k = top_k * 3 if rerank else top_k
        where = self._build_where(doc_ids, doc_types)

        try:
            embedding = self._embedder.embed(query)
            candidates = self._vector_store.query(
                query_embedding=embedding,
                query_text=query,
                top_k=fetch_k,
                where=where,
            )
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

        if rerank and len(candidates) > top_k:
            candidates = self._rerank(query, candidates, top_k)

        return candidates[:top_k]

    def _rerank(self, query: str, candidates: list[SearchResult], top_k: int) -> list[SearchResult]:
        """Re-rank candidates using cross-encoder."""
        reranker = self._load_reranker()
        if reranker is None:
            return candidates[:top_k]

        try:
            pairs = [(query, r.text) for r in candidates]
            scores = reranker.predict(pairs)
            reranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
            results = []
            for result, score in reranked[:top_k]:
                result.score = float(score)
                results.append(result)
            return results
        except Exception as e:
            logger.warning(f"Re-ranking failed: {e}")
            return candidates[:top_k]

    def _build_where(
        self,
        doc_ids: Optional[list[str]],
        doc_types: Optional[list[str]],
    ) -> Optional[dict]:
        """Build ChromaDB where filter."""
        conditions: list[dict] = []
        if doc_ids:
            if len(doc_ids) == 1:
                conditions.append({"doc_id": {"$eq": doc_ids[0]}})
            else:
                conditions.append({"doc_id": {"$in": doc_ids}})
        if doc_types:
            if len(doc_types) == 1:
                conditions.append({"doc_type": {"$eq": doc_types[0]}})
            else:
                conditions.append({"doc_type": {"$in": doc_types}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
