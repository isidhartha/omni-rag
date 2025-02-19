"""Graph-based retrieval for multi-hop reasoning across knowledge graph."""
from __future__ import annotations

import logging
from typing import Optional

from backend.shared.models import SearchResult

logger = logging.getLogger("omnirag.retrieval.graph")


class GraphRetrieval:
    """Multi-hop graph traversal over the knowledge graph for complex queries."""

    def __init__(self, knowledge_graph, vector_store, embedder) -> None:
        self._graph = knowledge_graph
        self._vector_store = vector_store
        self._embedder = embedder

    def search(
        self,
        query: str,
        top_k: int = 10,
        max_hops: int = 2,
    ) -> list[SearchResult]:
        """Retrieve via graph traversal: seed from vector search, then expand."""
        seed_results = self._seed_search(query, top_k=top_k)
        if not seed_results or max_hops == 0:
            return seed_results

        expanded = self._expand_via_graph(seed_results, query, max_hops, top_k)
        return expanded

    def _seed_search(self, query: str, top_k: int) -> list[SearchResult]:
        """Initial vector similarity search to seed graph traversal."""
        try:
            embedding = self._embedder.embed(query)
            return self._vector_store.query(
                query_embedding=embedding,
                query_text=query,
                top_k=top_k,
            )
        except Exception as e:
            logger.error(f"Seed search failed: {e}")
            return []

    def _expand_via_graph(
        self,
        seeds: list[SearchResult],
        query: str,
        max_hops: int,
        top_k: int,
    ) -> list[SearchResult]:
        """Expand search results by traversing related nodes in knowledge graph."""
        seen_ids: set[str] = {r.chunk_id for r in seeds}
        current_level = list(seeds)
        all_results: list[SearchResult] = list(seeds)

        for hop in range(max_hops):
            next_level: list[SearchResult] = []
            for result in current_level:
                related_doc_ids = self._graph.get_related_docs(result.doc_id)
                for related_doc_id in related_doc_ids[:3]:
                    try:
                        embedding = self._embedder.embed(query)
                        hop_results = self._vector_store.query(
                            query_embedding=embedding,
                            query_text=query,
                            top_k=3,
                            where={"doc_id": {"$eq": related_doc_id}},
                        )
                        for hr in hop_results:
                            if hr.chunk_id not in seen_ids:
                                seen_ids.add(hr.chunk_id)
                                # Decay score by hop distance
                                hr.score *= 0.7 ** (hop + 1)
                                next_level.append(hr)
                    except Exception as e:
                        logger.debug(f"Graph hop failed for doc {related_doc_id}: {e}")

            all_results.extend(next_level)
            current_level = next_level

            if len(all_results) >= top_k * 2:
                break

        # Re-rank by score and return top_k
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:top_k]
