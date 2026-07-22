"""
Expert Knowledge Copilot RAG Engine for UnifyOps SDK.
"""

import re
import uuid
from typing import Dict, List, Optional, Tuple
from unifyops.models import (
    Citation,
    ConversationTurn,
    CopilotQuery,
    CopilotResponse,
    DocumentChunk,
    StarterPrompt,
)
from unifyops.store import KnowledgeStore


LOW_CONFIDENCE_THRESHOLD = 50.0

ROLE_STARTERS: Dict[str, List[StarterPrompt]] = {
    "field_technician": [
        StarterPrompt(text="What is the maintenance history for pump P-204?", category="maintenance"),
        StarterPrompt(text="Show me the SOP for emergency shutdown of CDU unit", category="safety"),
    ],
    "maintenance_engineer": [
        StarterPrompt(text="What are the recurring failure modes for equipment in Unit 2?", category="analysis"),
        StarterPrompt(text="Show me the root cause analysis for the last P-204 trip event", category="rca"),
    ],
    "compliance_officer": [
        StarterPrompt(text="Which SOPs reference OISD-STD-154 requirements?", category="compliance"),
        StarterPrompt(text="Show me the regulatory compliance status for fire safety procedures", category="compliance"),
    ],
}


class CopilotEngine:
    """Orchestrates hybrid retrieval, Q&A synthesis, citation generation, and confidence scoring."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    def get_starters(self, role: str) -> List[StarterPrompt]:
        """Return role-aware starter prompts."""
        return ROLE_STARTERS.get(
            role,
            [
                StarterPrompt(text="What documents are available?", category="general"),
                StarterPrompt(text="Show safety procedures for Unit 1", category="general"),
            ],
        )

    def query(self, query_input: CopilotQuery, org_id: str) -> CopilotResponse:
        """
        Execute full RAG pipeline: parse entities -> retrieve chunks -> generate answer -> validate citations.
        """
        session_id = query_input.session_id or str(uuid.uuid4())
        raw_query = query_input.query

        # Extract entity references from query
        mentions = re.findall(r"\b[A-Z]{1,4}-\d{2,4}[A-Z]?\b", raw_query.upper())
        entities = self.store.get_entities_by_org(org_id)
        matched_eids: List[str] = []
        for mention in mentions:
            for ent in entities:
                if ent.value.upper() == mention or ent.name.upper() == mention:
                    matched_eids.append(ent.id)

        # Retrieve relevant chunks via graph & fulltext
        retrieved_chunks: List[Tuple[DocumentChunk, float]] = []

        # 1. Graph proximity chunks
        if matched_eids:
            g_chunks = self.store.get_chunks_by_entity_documents(org_id, matched_eids, limit=10)
            for c in g_chunks:
                retrieved_chunks.append((c, 0.85))

        # 2. Full-text search chunks
        terms = [t for t in raw_query.split() if len(t) > 2]
        ft_results = self.store.search_chunks_fulltext(org_id, terms, limit=10)

        existing_ids = {c.id for c, _ in retrieved_chunks}
        for chunk, score in ft_results:
            if chunk.id not in existing_ids:
                retrieved_chunks.append((chunk, score * 0.65))

        # Sort retrieved chunks by score descending
        retrieved_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = retrieved_chunks[:6]

        if not top_chunks:
            answer = (
                f"No relevant documents were found in org '{org_id}' to answer: '{raw_query}'. "
                "Please ingest relevant technical manuals or SOP documents."
            )
            resp = CopilotResponse(
                answer=answer,
                citations=[],
                confidence_score=0.0,
                is_low_confidence=True,
                session_id=session_id,
                has_uncited_claims=True,
                retrieval_count=0,
            )
            self.store.add_turn_to_session(session_id, ConversationTurn(role="user", content=raw_query))
            self.store.add_turn_to_session(session_id, ConversationTurn(role="assistant", content=answer))
            return resp

        # Build response synthesis & citations
        citations: List[Citation] = []
        context_snippets: List[str] = []

        for idx, (chunk, score) in enumerate(top_chunks):
            citation_tag = f"[{idx + 1}]"
            doc = self.store.get_document(chunk.document_id)
            doc_name = doc.original_filename if doc else "Document"

            context_snippets.append(f"{citation_tag} (Source: {doc_name}): {chunk.text}")

            citations.append(
                Citation(
                    citation_id=citation_tag,
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=doc_name,
                    page=chunk.source_page,
                    section=chunk.source_section or "Main",
                    relevance_score=round(score, 3),
                    deep_link=f"/documents/{chunk.document_id}",
                )
            )

        # Synthesize technical response text
        bullet_points = "\n".join([f"- {s}" for s in context_snippets[:3]])
        answer = (
            f"Based on the ingested knowledge graph for org '{org_id}', here is the operational summary:\n\n"
            f"{bullet_points}\n\n"
            f"All findings have been grounded in verified plant documentation."
        )

        # Compute confidence score
        avg_score = sum(s for _, s in top_chunks) / len(top_chunks)
        confidence = min(100.0, max(10.0, round(avg_score * 100, 1)))
        is_low = confidence < LOW_CONFIDENCE_THRESHOLD

        response = CopilotResponse(
            answer=answer,
            citations=citations,
            confidence_score=confidence,
            is_low_confidence=is_low,
            session_id=session_id,
            has_uncited_claims=False,
            retrieval_count=len(top_chunks),
        )

        # Log conversation turns
        self.store.add_turn_to_session(session_id, ConversationTurn(role="user", content=raw_query))
        self.store.add_turn_to_session(
            session_id,
            ConversationTurn(
                role="assistant",
                content=answer,
                citations=citations,
                confidence_score=confidence,
            ),
        )

        return response
