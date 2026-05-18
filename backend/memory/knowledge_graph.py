"""In-memory knowledge graph for document relationship tracking."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger("omnirag.memory.kg")


class KnowledgeGraph:
    """Lightweight knowledge graph tracking document relationships and entity co-occurrence."""

    def __init__(self) -> None:
        # Adjacency list: doc_id -> set of related doc_ids
        self._edges: dict[str, set[str]] = defaultdict(set)
        # Entity index: entity -> set of doc_ids mentioning it
        self._entity_docs: dict[str, set[str]] = defaultdict(set)
        # Doc metadata cache
        self._doc_meta: dict[str, dict] = {}

    def add_document(self, doc_id: str, entities: list[str], metadata: Optional[dict] = None) -> None:
        """Register a document with its extracted entities."""
        self._doc_meta[doc_id] = metadata or {}

        for entity in entities:
            entity_key = entity.lower().strip()
            self._entity_docs[entity_key].add(doc_id)

        # Create edges between docs sharing entities
        for entity in entities:
            entity_key = entity.lower().strip()
            for related_doc_id in self._entity_docs[entity_key]:
                if related_doc_id != doc_id:
                    self._edges[doc_id].add(related_doc_id)
                    self._edges[related_doc_id].add(doc_id)

        logger.debug(f"Added doc {doc_id} with {len(entities)} entities to KG.")

    def get_related_docs(self, doc_id: str, max_results: int = 5) -> list[str]:
        """Return doc IDs related to a given document."""
        related = list(self._edges.get(doc_id, set()))
        return related[:max_results]

    def get_docs_by_entity(self, entity: str) -> list[str]:
        """Return all doc IDs mentioning an entity."""
        return list(self._entity_docs.get(entity.lower().strip(), set()))

    def get_entity_graph(self, doc_id: str) -> dict:
        """Return graph structure centered on a document for visualization."""
        nodes: list[dict] = []
        links: list[dict] = []
        seen: set[str] = set()

        def add_node(nid: str, level: int = 0) -> None:
            if nid in seen:
                return
            seen.add(nid)
            meta = self._doc_meta.get(nid, {})
            nodes.append({
                "id": nid,
                "label": meta.get("filename", nid[:8]),
                "type": meta.get("doc_type", "unknown"),
                "level": level,
            })

        add_node(doc_id, level=0)
        for related_id in self.get_related_docs(doc_id):
            add_node(related_id, level=1)
            links.append({"source": doc_id, "target": related_id, "weight": 1})

        return {"nodes": nodes, "links": links}

    def remove_document(self, doc_id: str) -> None:
        """Remove a document and all its graph edges."""
        # Remove from edge lists of related docs
        for related_id in self._edges.get(doc_id, set()):
            self._edges[related_id].discard(doc_id)
        self._edges.pop(doc_id, None)

        # Remove from entity index
        for entity, docs in self._entity_docs.items():
            docs.discard(doc_id)

        self._doc_meta.pop(doc_id, None)
        logger.info(f"Removed doc {doc_id} from knowledge graph.")

    def stats(self) -> dict:
        """Return graph statistics."""
        return {
            "total_documents": len(self._doc_meta),
            "total_edges": sum(len(v) for v in self._edges.values()) // 2,
            "total_entities": len(self._entity_docs),
        }
