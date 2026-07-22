"""
In-memory and file-persistent Knowledge Graph Store for UnifyOps SDK.
"""

from typing import Dict, List, Optional, Tuple
from unifyops.models import (
    ConversationTurn,
    Document,
    DocumentChunk,
    EntityNode,
    KnowledgeRelationship,
)
from unifyops.exceptions import EntityNotFoundError


class KnowledgeStore:
    """Embedded Knowledge Graph Store and Document Chunk Registry."""

    def __init__(self) -> None:
        self.documents: Dict[str, Document] = {}
        self.chunks: Dict[str, DocumentChunk] = {}
        self.entities: Dict[str, EntityNode] = {}
        self.relationships: Dict[str, KnowledgeRelationship] = {}
        self.sessions: Dict[str, List[ConversationTurn]] = {}

    def clear(self) -> None:
        """Clear all stored data."""
        self.documents.clear()
        self.chunks.clear()
        self.entities.clear()
        self.relationships.clear()
        self.sessions.clear()

    # ── Documents ──

    def add_document(self, document: Document) -> None:
        self.documents[document.id] = document

    def get_document(self, document_id: str) -> Optional[Document]:
        return self.documents.get(document_id)

    def list_documents(self, org_id: str) -> List[Document]:
        return [d for d in self.documents.values() if d.org_id == org_id]

    # ── Chunks ──

    def add_chunk(self, chunk: DocumentChunk) -> None:
        self.chunks[chunk.id] = chunk
        if chunk.document_id in self.documents:
            self.documents[chunk.document_id].chunk_count += 1

    def get_chunk(self, chunk_id: str) -> Optional[DocumentChunk]:
        return self.chunks.get(chunk_id)

    def get_chunks_for_document(self, document_id: str) -> List[DocumentChunk]:
        return [c for c in self.chunks.values() if c.document_id == document_id]

    def get_all_chunks(self, org_id: str) -> List[DocumentChunk]:
        return [c for c in self.chunks.values() if c.org_id == org_id]

    def get_chunks_by_entity_documents(
        self, org_id: str, entity_ids: List[str], limit: int = 15
    ) -> List[DocumentChunk]:
        matching_doc_ids: set[str] = set()
        for eid in entity_ids:
            entity = self.entities.get(eid)
            if entity:
                matching_doc_ids.update(entity.linked_document_ids)

        chunks = [
            c for c in self.chunks.values()
            if c.org_id == org_id and c.document_id in matching_doc_ids
        ]
        return chunks[:limit]

    def search_chunks_fulltext(
        self, org_id: str, query_terms: List[str], limit: int = 20
    ) -> List[Tuple[DocumentChunk, float]]:
        if not query_terms:
            return []

        results: List[Tuple[DocumentChunk, float]] = []
        for chunk in self.chunks.values():
            if chunk.org_id != org_id:
                continue

            text_lower = chunk.text.lower()
            match_count = 0
            for term in query_terms:
                if term.lower() in text_lower:
                    match_count += 1

            if match_count > 0:
                score = match_count / float(len(query_terms))
                results.append((chunk, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    # ── Entities ──

    def add_entity(self, entity: EntityNode) -> None:
        self.entities[entity.id] = entity

    def get_entity(self, entity_id: str) -> Optional[EntityNode]:
        return self.entities.get(entity_id)

    def get_entities_by_org(self, org_id: str) -> List[EntityNode]:
        return [e for e in self.entities.values() if e.org_id == org_id]

    # ── Relationships ──

    def add_relationship(self, rel: KnowledgeRelationship) -> None:
        self.relationships[rel.id] = rel

    def get_entity_relationships(self, entity_id: str) -> List[KnowledgeRelationship]:
        return [
            r for r in self.relationships.values()
            if r.source_entity_id == entity_id or r.target_entity_id == entity_id
        ]

    # ── Sessions ──

    def get_session_turns(self, session_id: str) -> List[ConversationTurn]:
        return self.sessions.get(session_id, [])

    def add_turn_to_session(self, session_id: str, turn: ConversationTurn) -> None:
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(turn)
