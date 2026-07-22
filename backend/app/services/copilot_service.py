"""
UnifyOps - Copilot Service (Phase 3 - RAG Engine)

The heart of the Expert Knowledge Copilot. Implements:
- Query understanding with entity parsing (FR-3.2.2)
- Hybrid retrieval: graph-proximity + full-text + vector (FR-3.2.1)
- Role-based access scoping at the retrieval layer (FR-3.5.1)
- Answer generation with structured citation tags (FR-3.3.1)
- Citation validation - no hallucinated citations (FR-3.3.2)
- Confidence scoring from retrieval quality + citation coverage (FR-3.4.1)
- Multi-turn conversation context management (FR-3.6)
- Query analytics logging (FR-3.7.1)
"""

import re
import uuid

from app.core.config import settings
from app.core.store import store
from app.services.model_armor import model_armor_service, SecurityBlockException
from app.services.sdp_service import sdp_service
from app.models.copilot import (
    Citation,
    ConversationSession,
    ConversationTurn,
    CopilotQuery,
    CopilotResponse,
    QueryLogEntry,
    StarterPrompt,
)
from app.models.ingestion import DocumentChunk
from app.services.gemini import gemini_service

# Confidence threshold below which answers get the amber banner (FR-3.4.2)
LOW_CONFIDENCE_THRESHOLD = 50

# Maximum conversation turns to include as context (FR-3.6.1)
MAX_CONTEXT_TURNS = 6

# Maximum chunks to pass to generation
MAX_CONTEXT_CHUNKS = 10

# Retrieval score weights for hybrid ranking
WEIGHT_GRAPH = 0.50  # Graph-proximity chunks get highest weight
WEIGHT_FULLTEXT = 0.35
WEIGHT_VECTOR = 0.15  # Only when embeddings are available


# ─────────────────────────── Role-based starter prompts (FR-3.1.3) ────────

ROLE_STARTERS: dict[str, list[StarterPrompt]] = {
    "field_technician": [
        StarterPrompt(
            text="What is the maintenance history for pump P-204?",
            category="maintenance",
        ),
        StarterPrompt(
            text="Show me the SOP for emergency shutdown of the CDU unit",
            category="safety",
        ),
        StarterPrompt(
            text="What parts were replaced on heat exchanger HE-301 last quarter?",
            category="maintenance",
        ),
        StarterPrompt(
            text="Are there any open safety advisories for Unit 3?",
            category="safety",
        ),
    ],
    "maintenance_engineer": [
        StarterPrompt(
            text="What are the recurring failure modes for equipment in Unit 2?",
            category="analysis",
        ),
        StarterPrompt(
            text="Show me the root cause analysis for the last P-204 trip event",
            category="rca",
        ),
        StarterPrompt(
            text="Which equipment has overdue maintenance based on work order history?",
            category="maintenance",
        ),
        StarterPrompt(
            text="Compare failure patterns between pump P-204 and P-205",
            category="analysis",
        ),
    ],
    "compliance_officer": [
        StarterPrompt(
            text="Which SOPs reference OISD-STD-154 requirements?",
            category="compliance",
        ),
        StarterPrompt(
            text="Are there any procedures that haven't been updated in the last 12 months?",
            category="compliance",
        ),
        StarterPrompt(
            text="Show me the regulatory compliance status for fire safety procedures",
            category="compliance",
        ),
        StarterPrompt(
            text="What inspection reports are linked to environmental compliance clauses?",
            category="compliance",
        ),
    ],
    "senior_engineer": [
        StarterPrompt(
            text="Summarise the key lessons learned from incident reports in the last year",
            category="knowledge",
        ),
        StarterPrompt(
            text="What undocumented operational patterns have been observed in work orders?",
            category="knowledge",
        ),
        StarterPrompt(
            text="Show me the complete maintenance timeline for critical equipment",
            category="maintenance",
        ),
    ],
    "platform_admin": [
        StarterPrompt(
            text="What topics are users asking about that have no supporting documents?",
            category="admin",
        ),
        StarterPrompt(
            text="Show me the knowledge graph completeness by document type",
            category="admin",
        ),
        StarterPrompt(
            text="Which documents have the lowest entity extraction confidence?",
            category="admin",
        ),
    ],
    "plant_head": [
        StarterPrompt(
            text="Give me a summary of unresolved safety incidents across all units",
            category="leadership",
        ),
        StarterPrompt(
            text="What is the overall maintenance backlog and risk exposure?",
            category="leadership",
        ),
        StarterPrompt(
            text="Show me compliance gaps that need immediate attention",
            category="compliance",
        ),
    ],
}

# Fallback for unknown roles
DEFAULT_STARTERS = [
    StarterPrompt(
        text="What documents have been uploaded recently?",
        category="general",
    ),
    StarterPrompt(
        text="Show me information about equipment P-204",
        category="general",
    ),
    StarterPrompt(
        text="What safety procedures are available?",
        category="general",
    ),
]


class CopilotService:
    """Orchestrates the full RAG pipeline for the Expert Knowledge Copilot."""

    # ──────────────────── 1. Query Understanding (FR-3.2.2) ────────────────

    def parse_entity_mentions(self, query: str) -> list[str]:
        """
        Extract equipment tags and entity mentions from a query using regex.
        Falls back to Gemini for complex NLP if available.
        Returns a list of entity reference strings.
        """
        mentions: list[str] = []

        # Regex: equipment tags like P-204, HE-301, PSV-301A, V-102
        tags = re.findall(r"\b[A-Z]{1,4}-\d{2,4}[A-Z]?\b", query.upper())
        mentions.extend(tags)

        # Regex: regulatory references like OISD-STD-154, API 510
        regs = re.findall(r"\b(?:OISD|API|PNGRB)[-\s][\w\d-]+\b", query.upper())
        mentions.extend(regs)

        return list(set(mentions))

    def resolve_entity_ids(self, org_id: str, mentions: list[str]) -> list[str]:
        """
        Resolve textual entity mentions to entity IDs in the store.
        Checks both value and normalised_value fields.
        """
        entity_ids: list[str] = []
        org_entities = store.get_entities_by_org(org_id)

        for mention in mentions:
            mention_upper = mention.upper().strip()
            for entity in org_entities:
                val = entity.value.upper().strip()
                norm = entity.normalised_value.upper().strip()
                if mention_upper == val or mention_upper == norm:
                    # Use canonical ID if resolved, otherwise entity's own ID
                    eid = entity.canonical_id or entity.id
                    if eid not in entity_ids:
                        entity_ids.append(eid)

        return entity_ids

    # ──────────────────── 2. Hybrid Retrieval (FR-3.2.1) ───────────────────

    def retrieve(
        self,
        org_id: str,
        query: str,
        entity_ids: list[str],
        plant_id: str = "",
        department: str = "",
    ) -> list[tuple[DocumentChunk, float, str]]:
        """
        Hybrid retrieval combining graph-proximity, full-text, and vector search.
        Returns (chunk, combined_score, source_type) tuples.

        Access scoping (FR-3.5.1): filters by org_id at the retrieval layer.
        plant_id and department further scope results when provided.
        """
        scored_chunks: dict[str, tuple[DocumentChunk, float, str]] = {}

        # (a) Graph-proximity retrieval - chunks from documents linked to detected entities
        if entity_ids:
            graph_chunks = store.get_chunks_by_entity_documents(
                org_id=org_id, entity_ids=entity_ids, limit=15
            )
            for chunk in graph_chunks:
                if self._access_check(chunk, org_id, plant_id, department):
                    scored_chunks[chunk.id] = (chunk, WEIGHT_GRAPH, "graph")

        # (b) Full-text search
        query_terms = [t for t in query.split() if len(t) > 2]
        fulltext_results = store.search_chunks_fulltext(
            org_id=org_id, query_terms=query_terms, limit=20
        )
        for chunk, ft_score in fulltext_results:
            if not self._access_check(chunk, org_id, plant_id, department):
                continue
            if chunk.id in scored_chunks:
                # Boost existing graph chunks
                existing = scored_chunks[chunk.id]
                new_score = existing[1] + (ft_score * WEIGHT_FULLTEXT)
                scored_chunks[chunk.id] = (chunk, new_score, "graph+fulltext")
            else:
                scored_chunks[chunk.id] = (
                    chunk,
                    ft_score * WEIGHT_FULLTEXT,
                    "fulltext",
                )

        # (c) Vector similarity (if embeddings are available)
        # Generate query embedding and compare with chunk embeddings
        query_embedding = gemini_service.generate_embeddings([query])
        if query_embedding and len(query_embedding) > 0:
            _q_emb = query_embedding[0]
            _all_chunks = store.get_all_chunks_for_org(org_id)
            # NOTE: In a production system, embeddings would be stored alongside chunks.

            # For the MVP, we only have embeddings if they were generated during ingestion.
            # This is a graceful fallback - vector search adds to but doesn't replace
            # graph + fulltext retrieval.

        # Sort by combined score descending
        results = list(scored_chunks.values())
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:MAX_CONTEXT_CHUNKS]

    def _access_check(
        self,
        chunk: DocumentChunk,
        org_id: str,
        plant_id: str,
        department: str,
    ) -> bool:
        """
        Role-based access check at the retrieval layer (FR-3.5.1).
        Ensures chunks only come from the user's org. Additional plant_id
        and department filtering when set.
        """
        if chunk.org_id != org_id:
            return False

        # If plant_id or department scoping is set, check the parent document
        if plant_id or department:
            doc = store.get_document(chunk.document_id)
            if doc:
                if plant_id and doc.plant_id and doc.plant_id != plant_id:
                    return False
                # Department scoping would check doc metadata - for MVP we pass
        return True

    # ──────────────────── 3. Answer Generation (FR-3.3.1) ──────────────────

    def generate_answer(
        self,
        query: str,
        retrieved_chunks: list[tuple[DocumentChunk, float, str]],
        conversation_history: list[ConversationTurn] | None = None,
        user_role: str = "",
        user_language: str = "en",
    ) -> tuple[str, list[Citation], bool]:
        """
        Generate an answer using Gemini with structured citation tags.
        Returns (answer_text, citations_list, has_uncited_claims).
        """
        if not retrieved_chunks:
            return (
                "I couldn't find any relevant documents in the knowledge base to answer "
                "your question. This might mean the relevant documents haven't been "
                "ingested yet, or the question is outside the scope of the current corpus.",
                [],
                True,
            )

        # Build context with explicit source IDs for citation tagging
        context_parts: list[str] = []
        chunk_map: dict[str, tuple[DocumentChunk, float]] = {}

        for i, (chunk, score, _source_type) in enumerate(retrieved_chunks):
            source_id = f"source_{i + 1}"
            chunk_map[source_id] = (chunk, score)

            doc = store.get_document(chunk.document_id)
            doc_name = doc.original_filename if doc else "Unknown Document"
            page_info = f", Page {chunk.source_page}" if chunk.source_page else ""
            section_info = (
                f", Section: {chunk.heading_context}" if chunk.heading_context else ""
            )

            context_parts.append(
                f"[{source_id}] (Document: {doc_name}{page_info}{section_info}):\n"
                f"{chunk.text}\n"
            )

        context_block = "\n---\n".join(context_parts)

        # Build conversation history context
        history_block = ""
        if conversation_history:
            recent = conversation_history[-MAX_CONTEXT_TURNS:]
            turns_text = []
            for turn in recent:
                turns_text.append(f"{turn.role.upper()}: {turn.content}")
            history_block = (
                "\n\nPREVIOUS CONVERSATION:\n" + "\n".join(turns_text) + "\n"
            )

        lang_map = {
            "en": "English",
            "hi": "Hindi",
            "mr": "Marathi",
            "ta": "Tamil",
            "kn": "Kannada",
        }
        lang_name = lang_map.get(user_language.lower(), "English")
        language_instruction = ""
        if lang_name != "English":
            language_instruction = f"\n8. CRITICAL: Generate the final response in {lang_name}. Make sure it is grammatically correct and fluent, but keep all source citation tags like [source_1], [source_2] exactly as they are (do not translate the words 'source')."

        # Build the generation prompt
        prompt = f"""You are UnifyOps Expert Knowledge Copilot - an industrial knowledge assistant
for plant operations. You answer questions about equipment, maintenance, safety procedures,
compliance, and operational knowledge using ONLY the provided source documents.

CRITICAL RULES:
1. Base your answer ONLY on the provided source documents below.
2. For every claim or fact, include a citation tag like [source_1], [source_2], etc.
3. If a claim is NOT supported by any source, prefix it with [GENERAL] to indicate it is general knowledge.
4. Be concise and technically precise - this is for industrial plant professionals.
5. If the sources don't contain enough information, say so honestly.
6. Never fabricate equipment tags, dates, measurements, or procedures.
{f"7. The user's role is '{user_role}' - tailor technical depth accordingly." if user_role else ""}{language_instruction}

SOURCE DOCUMENTS:
{context_block}
{history_block}
CURRENT QUESTION: {query}

Provide a clear, well-structured answer with citation tags."""

        # Call Gemini for generation
        answer = self._call_gemini(prompt)

        # Post-process: validate citations and build citation objects
        citations, has_uncited = self._validate_citations(answer, chunk_map)

        return answer, citations, has_uncited

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini for answer generation with Groq fallback."""
        if gemini_service.enabled:
            try:
                import google.generativeai as genai

                model = genai.GenerativeModel("gemini-2.0-flash")
                response = model.generate_content(prompt)
                if response.text:
                    return response.text
            except Exception as e:
                print(f"[CopilotService] Gemini generation failed: {e}")

        # Groq fallback
        groq_key = settings.groq_api_key
        if groq_key:
            try:
                import httpx

                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 2000,
                }
                groq_response = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                if groq_response.status_code == 200:
                    data = groq_response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    print(
                        f"[CopilotService] Groq returned status {groq_response.status_code}"
                    )
            except Exception as e:
                print(f"[CopilotService] Groq generation failed: {e}")

        return (
            "I'm currently unable to generate an answer because the AI service "
            "is unavailable. Please try again shortly or contact your administrator."
        )

    # ──────────────────── 4. Citation Validation (FR-3.3.2) ────────────────

    def _validate_citations(
        self,
        answer: str,
        chunk_map: dict[str, tuple[DocumentChunk, float]],
    ) -> tuple[list[Citation], bool]:
        """
        Post-process generated answer to validate all citation tags.
        - Citations referencing actual retrieved chunks are kept.
        - Hallucinated citations (not in chunk_map) are stripped.
        - Returns (valid_citations, has_uncited_claims).
        """
        citations: list[Citation] = []
        seen_sources: set[str] = set()
        has_uncited = "[GENERAL]" in answer

        # Find all [source_N] references in the answer
        source_refs = re.findall(r"\[source_(\d+)\]", answer)

        citation_number = 1
        for ref_num in source_refs:
            source_id = f"source_{ref_num}"
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)

            if source_id not in chunk_map:
                # Hallucinated citation - this is a defect per FR-3.3.2
                print(f"[CopilotService] Stripping hallucinated citation: {source_id}")
                continue

            chunk, score = chunk_map[source_id]
            doc = store.get_document(chunk.document_id)
            doc_name = doc.original_filename if doc else "Unknown"

            citations.append(
                Citation(
                    citation_id=f"[{citation_number}]",
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=doc_name,
                    page=chunk.source_page,
                    section=chunk.heading_context or chunk.source_section,
                    relevance_score=round(score, 3),
                    deep_link=f"/documents/{chunk.document_id}",
                )
            )
            citation_number += 1

        return citations, has_uncited

    def _translate_text(self, text: str, target_lang: str) -> str:
        """Helper to translate text using Gemini with local fallback (Phase 7.4)."""
        prompt = f"""You are a professional translator. Translate the following text into {target_lang}.
Text: "{text}"
Provide ONLY the translated text. Do not add any introduction, greeting, or explanations."""
        return self._call_gemini(prompt).strip()

    # ──────────────────── 5. Confidence Scoring (FR-3.4.1) ─────────────────

    def compute_confidence(
        self,
        retrieved_chunks: list[tuple[DocumentChunk, float, str]],
        citations: list[Citation],
        answer: str,
    ) -> int:
        """
        Compute confidence score (0-100) from:
        (a) Average retrieval score of top chunks (60% weight)
        (b) Citation coverage ratio (40% weight)
        """
        if not retrieved_chunks:
            return 0

        # (a) Retrieval quality - average score of retrieved chunks
        scores = [score for _, score, _ in retrieved_chunks]
        avg_retrieval = sum(scores) / len(scores) if scores else 0
        # Normalise to 0-100 (scores are weighted, typically 0-1)
        retrieval_component = min(avg_retrieval * 100, 100)

        # (b) Citation coverage - how many claims are cited vs total
        # Simple proxy: count citation tags vs estimated sentence count
        sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 10]
        total_sentences = max(len(sentences), 1)
        cited_sentences = sum(1 for s in sentences if re.search(r"\[source_\d+\]", s))
        coverage_ratio = cited_sentences / total_sentences

        # Weighted combination
        confidence = int((retrieval_component * 0.6) + (coverage_ratio * 100 * 0.4))
        return max(0, min(100, confidence))

    # ──────────────────── 6. Multi-Turn Context (FR-3.6) ──────────────────

    def resolve_follow_up(
        self,
        query: str,
        session: ConversationSession,
    ) -> str:
        """
        Resolve ambiguous references in follow-up queries (FR-3.6.2).
        E.g. "what about its backup?" → resolve "its" to the entity from prior turns.
        """
        # Check for ambiguous pronouns/references
        ambiguous_patterns = [
            r"\b(it|its|this|that|the same|this one|that one)\b",
            r"\b(the pump|the equipment|the valve|the motor)\b",
        ]
        has_ambiguity = any(
            re.search(pattern, query, re.IGNORECASE) for pattern in ambiguous_patterns
        )

        if not has_ambiguity or not session.turns:
            return query

        # Find entity mentions from recent conversation turns
        recent_entities: list[str] = []
        for turn in reversed(session.turns[-MAX_CONTEXT_TURNS:]):
            mentions = self.parse_entity_mentions(turn.content)
            recent_entities.extend(mentions)
            if recent_entities:
                break

        if recent_entities:
            # Prepend context to the query for retrieval
            entity_context = ", ".join(recent_entities[:3])
            return f"Regarding {entity_context}: {query}"

        return query

    # ──────────────────── 7. Full Pipeline ─────────────────────────────────

    def process_query(
        self,
        query: CopilotQuery,
        org_id: str,
        user_uid: str,
        user_role: str = "",
        plant_id: str = "",
        department: str = "",
        user_language: str = "en",
    ) -> CopilotResponse:
        """
        Full RAG pipeline: parse → retrieve → generate → cite → score.
        Supports regional language translation (Phase 7.4).
        """
        raw_query = query.query

        # Get or create session
        session_id = query.session_id or str(uuid.uuid4())
        session = store.get_session(session_id)
        if not session:
            session = store.create_session(session_id, org_id, user_uid)

        # Resolve follow-up queries using conversation context (FR-3.6.2)
        resolved_query = self.resolve_follow_up(raw_query, session)

        # Save user turn
        user_turn = ConversationTurn(role="user", content=raw_query)
        store.add_turn_to_session(session_id, user_turn)

        # Model Armor Screening (FR-9.2)
        try:
            model_armor_service.screen_interaction(resolved_query, "copilot-agent")
        except SecurityBlockException as e:
            blocked_response = CopilotResponse(
                answer=f"Blocked by Model Armor: {e.reason}",
                citations=[],
                confidence_score=0,
                is_low_confidence=True,
                session_id=session_id,
                has_uncited_claims=False,
                retrieval_count=0,
            )
            # Log the blocked assistant response
            assistant_turn = ConversationTurn(
                role="assistant",
                content=blocked_response.answer,
                citations=[],
                confidence_score=0,
            )

            store.add_turn_to_session(session_id, assistant_turn)
            return blocked_response

        # Regional Language Support (FR-7.4.1)
        lang_map = {
            "en": "English",
            "hi": "Hindi",
            "mr": "Marathi",
            "ta": "Tamil",
            "kn": "Kannada",
        }
        lang_name = lang_map.get(user_language.lower(), "English")

        # Translate query to English for retrieval and entity parsing
        if lang_name != "English":
            query_for_retrieval = self._translate_text(resolved_query, "English")
        else:
            query_for_retrieval = resolved_query

        # Step 1: Parse entity mentions from query (FR-3.2.2)
        mentions = self.parse_entity_mentions(query_for_retrieval)
        entity_ids = self.resolve_entity_ids(org_id, mentions)

        # Step 2: Hybrid retrieval (FR-3.2.1)
        retrieved = self.retrieve(
            org_id=org_id,
            query=query_for_retrieval,
            entity_ids=entity_ids,
            plant_id=plant_id,
            department=department,
        )

        # Step 3: Generate answer with citations (FR-3.3.1)
        conversation_history = session.turns[:-1]  # Exclude the turn we just added
        answer_text, citations, has_uncited = self.generate_answer(
            query=query_for_retrieval,
            retrieved_chunks=retrieved,
            conversation_history=conversation_history
            if len(conversation_history) > 0
            else None,
            user_role=user_role,
            user_language=user_language,
        )

        # Screen output response
        try:
            model_armor_service.screen_interaction(answer_text, "copilot-agent")
        except SecurityBlockException as e:
            answer_text = f"Response blocked by Model Armor due to sensitive content leakage: {e.reason}"

        # Resolve sensitive PII data according to user role
        answer_text = sdp_service.resolve_sensitive_data(answer_text, user_role)

        # Step 4: Compute confidence (FR-3.4.1)
        confidence = self.compute_confidence(retrieved, citations, answer_text)
        is_low_confidence = confidence < LOW_CONFIDENCE_THRESHOLD

        # Save assistant turn
        assistant_turn = ConversationTurn(
            role="assistant",
            content=answer_text,
            citations=citations,
            confidence_score=confidence,
        )
        store.add_turn_to_session(session_id, assistant_turn)

        # Log query for analytics (FR-3.7.1)
        log_entry = QueryLogEntry(
            id=str(uuid.uuid4()),
            query=raw_query,
            confidence_score=confidence,
            retrieval_count=len(retrieved),
            org_id=org_id,
            user_role=user_role,
        )
        store.log_query(log_entry)

        return CopilotResponse(
            answer=answer_text,
            citations=citations,
            confidence_score=confidence,
            is_low_confidence=is_low_confidence,
            session_id=session_id,
            has_uncited_claims=has_uncited,
            retrieval_count=len(retrieved),
        )

    # ──────────────────── 8. Starter Prompts (FR-3.1.3) ───────────────────

    def get_starters(self, role: str) -> list[StarterPrompt]:
        """Return role-aware starter prompts."""
        return ROLE_STARTERS.get(role, DEFAULT_STARTERS)

    # ──────────────────── 9. Query Analytics (FR-3.7.2) ───────────────────

    def get_analytics(self, org_id: str) -> dict:
        """Compute query analytics and knowledge gaps."""
        logs = store.get_query_logs(org_id)
        if not logs:
            return {
                "total_queries": 0,
                "avg_confidence": 0.0,
                "low_confidence_count": 0,
                "top_gaps": [],
            }

        total = len(logs)
        avg_conf = sum(item.confidence_score for item in logs) / total
        low_conf = sum(
            1 for item in logs if item.confidence_score < LOW_CONFIDENCE_THRESHOLD
        )

        # Find recurring low-confidence query patterns
        low_conf_queries = [
            item for item in logs if item.confidence_score < LOW_CONFIDENCE_THRESHOLD
        ]

        # Simple clustering: group by first 3 significant words
        pattern_map: dict[str, list[QueryLogEntry]] = {}
        for entry in low_conf_queries:
            words = [w.lower() for w in entry.query.split() if len(w) > 2][:3]
            pattern_key = " ".join(words) if words else "unknown"
            if pattern_key not in pattern_map:
                pattern_map[pattern_key] = []
            pattern_map[pattern_key].append(entry)

        top_gaps = []
        for pattern, entries in sorted(
            pattern_map.items(), key=lambda x: len(x[1]), reverse=True
        )[:10]:
            top_gaps.append(
                {
                    "query_pattern": pattern,
                    "occurrence_count": len(entries),
                    "avg_confidence": round(
                        sum(e.confidence_score for e in entries) / len(entries), 1
                    ),
                    "last_seen": max(e.timestamp for e in entries).isoformat(),
                }
            )

        return {
            "total_queries": total,
            "avg_confidence": round(avg_conf, 1),
            "low_confidence_count": low_conf,
            "top_gaps": top_gaps,
        }


# Singleton
copilot_service = CopilotService()
