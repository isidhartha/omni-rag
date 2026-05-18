"""Hybrid search: BM25 sparse retrieval + dense vector search fused via RRF."""
from __future__ import annotations

import logging
import math
from typing import Optional

from backend.shared.models import SearchResult

logger = logging.getLogger("omnirag.retrieval.hybrid")

RRF_K = 60  # Reciprocal Rank Fusion constant


class HybridSearch:
    """Combines dense (vector) and sparse (BM25) retrieval with Reciprocal Rank Fusion."""

    def __init__(self, vector_store, embedder) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._bm25_index: dict[str, object] = {}  # doc_id -> BM25 model
        self._corpus: list[dict] = []  # [{chunk_id, text, doc_id, ...}]

    def add_to_bm25_index(self, chunks_with_meta: list[dict]) -> None:
        """Add chunks to in-memory BM25 corpus."""
        self._corpus.extend(chunks_with_meta)
        self._rebuild_bm25()

    def _rebuild_bm25(self) -> None:
        """Rebuild BM25 index from current corpus."""
        if not self._corpus:
            return
        try:
            from rank_bm25 import BM25Okapi
            tokenized = [doc["text"].lower().split() for doc in self._corpus]
            self._bm25 = BM25Okapi(tokenized)
        except ImportError:
            logger.warning("rank-bm25 not installed; sparse search unavailable.")
            self._bm25 = None

    def search(
        self,
        query: str,
        top_k: int = 10,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        where: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Run hybrid search and return RRF-fused results."""
        dense_results = self._dense_search(query, top_k=top_k * 2, where=where)
        sparse_results = self._sparse_search(query, top_k=top_k * 2)

        fused = self._reciprocal_rank_fusion(dense_results, sparse_results, top_k=top_k)
        return fused

    def _dense_search(self, query: str, top_k: int, where: Optional[dict]) -> list[SearchResult]:
        """Run dense vector search."""
        try:
            embedding = self._embedder.embed(query)
            return self._vector_store.query(
                query_embedding=embedding,
                query_text=query,
                top_k=top_k,
                where=where,
            )
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return []

    def _sparse_search(self, query: str, top_k: int) -> list[SearchResult]:
        """Run BM25 sparse search over corpus."""
        if not self._corpus or not getattr(self, "_bm25", None):
            return []

        try:
            tokenized_query = query.lower().split()
            scores = self._bm25.get_scores(tokenized_query)
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

            results: list[SearchResult] = []
            from backend.shared.models import ChunkMetadata, DocumentType
            for idx in top_indices:
                if scores[idx] <= 0:
                    continue
                doc = self._corpus[idx]
                chunk_meta = ChunkMetadata(
                    doc_id=doc.get("doc_id", ""),
                    chunk_index=doc.get("chunk_index", 0),
                    source=doc.get("source"),
                    page_number=doc.get("page_number"),
                )
                results.append(
                    SearchResult(
                        chunk_id=doc.get("chunk_id", f"bm25_{idx}"),
                        text=doc["text"],
                        score=float(scores[idx]),
                        doc_id=doc.get("doc_id", ""),
                        filename=doc.get("filename", ""),
                        doc_type=DocumentType(doc.get("doc_type", "text")),
                        metadata=chunk_meta,
                    )
                )
            return results
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        dense: list[SearchResult],
        sparse: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Fuse rankings from dense and sparse using RRF."""
        scores: dict[str, float] = {}
        chunk_map: dict[str, SearchResult] = {}

        for rank, result in enumerate(dense, start=1):
            rrf_score = 1.0 / (RRF_K + rank)
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + rrf_score
            chunk_map[result.chunk_id] = result

        for rank, result in enumerate(sparse, start=1):
            rrf_score = 1.0 / (RRF_K + rank)
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + rrf_score
            if result.chunk_id not in chunk_map:
                chunk_map[result.chunk_id] = result

        sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_k]

        fused: list[SearchResult] = []
        for cid in sorted_ids:
            result = chunk_map[cid]
            result.score = scores[cid]
            fused.append(result)

        return fused
