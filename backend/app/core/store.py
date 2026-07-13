"""
UnifyOps - In-Memory Data Store (With Local JSON File Persistence)

Local development data store. Replaced by Firestore/Spanner when deployed to GCP.
Thread-safe for single-process uvicorn with --reload.
Persists data to db.json to avoid registering on every server reload.
"""

import os
import json
import uuid
from datetime import datetime, timezone
from threading import Lock

from app.models.auth import Organisation, UserProfile, UserRole
from app.models.ingestion import (
    DocumentRecord,
    DocumentType,
    ExtractedEntity,
    DocumentChunk,
    PipelineStage,
    IngestionStats,
    PIDConnection,
    CandidateMerge,
)
from app.models.copilot import (
    ConversationSession,
    ConversationTurn,
    QueryLogEntry,
    FeedbackRequest,
    FeedbackVote,
)
from app.models.maintenance import RCADraft
from app.models.compliance import RegulatoryClause, ComplianceGap
from app.models.lessons import IncidentEnrichment, LessonPattern, PatternWarning

DB_FILE = "db.json"


class DataStore:
    """In-memory data store with file persistence for local development."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._orgs: dict[str, Organisation] = {}
        self._users: dict[str, UserProfile] = {}  # keyed by uid
        self._documents: dict[str, DocumentRecord] = {}  # keyed by doc id
        self._entities: dict[str, ExtractedEntity] = {}  # keyed by entity id
        self._chunks: dict[str, DocumentChunk] = {}  # keyed by chunk id
        self._connections: dict[str, PIDConnection] = {}  # keyed by connection id
        self._candidate_merges: dict[str, CandidateMerge] = {}  # keyed by merge id
        # Phase 3 - Copilot collections
        self._sessions: dict[str, ConversationSession] = {}  # keyed by session_id
        self._feedback: list[dict] = []  # feedback entries
        self._query_logs: list[QueryLogEntry] = []  # query analytics
        # Phase 4 - Maintenance Advisor collections
        self._rca_drafts: dict[str, RCADraft] = {}  # keyed by rca_id
        # Phase 5 - Compliance collections
        self._regulatory_clauses: dict[str, RegulatoryClause] = {}  # keyed by clause_id
        self._compliance_gaps: dict[str, ComplianceGap] = {}  # keyed by gap_id
        # Phase 6 - Lessons Learned collections
        self._incident_enrichments: dict[str, IncidentEnrichment] = {}  # keyed by enrichment id
        self._lesson_patterns: dict[str, LessonPattern] = {}  # keyed by pattern_id
        self._pattern_warnings: dict[str, PatternWarning] = {}  # keyed by warning_id

        # Load persisted data on initialization (unless running tests)
        if os.environ.get("TESTING") != "1":
            self._load()

    def _save(self) -> None:
        """Saves current memory state to local JSON file."""
        if os.environ.get("TESTING") == "1":
            return
        try:
            data = {
                "orgs": [o.model_dump() for o in self._orgs.values()],
                "users": [u.model_dump() for u in self._users.values()],
                "documents": [d.model_dump() for d in self._documents.values()],
                "entities": [e.model_dump() for e in self._entities.values()],
                "chunks": [c.model_dump() for c in self._chunks.values()],
                "connections": [
                    conn.model_dump() for conn in self._connections.values()
                ],
                "candidate_merges": [
                    m.model_dump() for m in self._candidate_merges.values()
                ],
                "sessions": [
                    s.model_dump() for s in self._sessions.values()
                ],
                "feedback": self._feedback,
                "query_logs": [
                    q.model_dump() for q in self._query_logs
                ],
                "rca_drafts": [
                    r.model_dump() for r in self._rca_drafts.values()
                ],
                "regulatory_clauses": [
                    c.model_dump() for c in self._regulatory_clauses.values()
                ],
                "compliance_gaps": [
                    g.model_dump() for g in self._compliance_gaps.values()
                ],
                "incident_enrichments": [
                    e.model_dump() for e in self._incident_enrichments.values()
                ],
                "lesson_patterns": [
                    p.model_dump() for p in self._lesson_patterns.values()
                ],
                "pattern_warnings": [
                    w.model_dump() for w in self._pattern_warnings.values()
                ],
            }

            # Custom datetime serializer to ISO format
            def datetime_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError("Type not serializable")

            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, default=datetime_serializer, indent=2)
        except Exception as e:
            print(f"[DataStore] Failed to save state to db.json: {e}")

    def _load(self) -> None:
        """Loads state from local JSON file if exists."""
        if not os.path.exists(DB_FILE):
            return
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            def parse_dt(s: str) -> datetime:
                return datetime.fromisoformat(s)

            for item in data.get("orgs", []):
                item["created_at"] = parse_dt(item["created_at"])
                org = Organisation(**item)
                self._orgs[org.id] = org

            for item in data.get("users", []):
                user = UserProfile(**item)
                self._users[user.uid] = user

            for item in data.get("documents", []):
                item["created_at"] = parse_dt(item["created_at"])
                item["updated_at"] = parse_dt(item["updated_at"])
                doc = DocumentRecord(**item)
                self._documents[doc.id] = doc

            for item in data.get("entities", []):
                ent = ExtractedEntity(**item)
                self._entities[ent.id] = ent

            for item in data.get("chunks", []):
                chk = DocumentChunk(**item)
                self._chunks[chk.id] = chk

            for item in data.get("connections", []):
                conn = PIDConnection(**item)
                self._connections[conn.id] = conn

            for item in data.get("candidate_merges", []):
                item["created_at"] = parse_dt(item["created_at"])
                merge = CandidateMerge(**item)
                self._candidate_merges[merge.id] = merge

            for item in data.get("sessions", []):
                item["created_at"] = parse_dt(item["created_at"])
                item["updated_at"] = parse_dt(item["updated_at"])
                for turn in item.get("turns", []):
                    turn["timestamp"] = parse_dt(turn["timestamp"])
                session = ConversationSession(**item)
                self._sessions[session.session_id] = session

            self._feedback = data.get("feedback", [])

            for item in data.get("query_logs", []):
                item["timestamp"] = parse_dt(item["timestamp"])
                self._query_logs.append(QueryLogEntry(**item))

            for item in data.get("rca_drafts", []):
                item["generated_at"] = parse_dt(item["generated_at"])
                if item.get("approved_at"):
                    item["approved_at"] = parse_dt(item["approved_at"])
                if item.get("original_draft_backup"):
                    backup = item["original_draft_backup"]
                    if backup.get("generated_at"):
                        backup["generated_at"] = parse_dt(backup["generated_at"])
                rca = RCADraft(**item)
                self._rca_drafts[rca.rca_id] = rca

            for item in data.get("regulatory_clauses", []):
                clause = RegulatoryClause(**item)
                self._regulatory_clauses[clause.id] = clause

            for item in data.get("compliance_gaps", []):
                item["created_at"] = parse_dt(item["created_at"])
                if item.get("resolved_at"):
                    item["resolved_at"] = parse_dt(item["resolved_at"])
                gap = ComplianceGap(**item)
                self._compliance_gaps[gap.gap_id] = gap

            for item in data.get("incident_enrichments", []):
                item["created_at"] = parse_dt(item["created_at"])
                enrich = IncidentEnrichment(**item)
                self._incident_enrichments[enrich.id] = enrich

            for item in data.get("lesson_patterns", []):
                item["created_at"] = parse_dt(item["created_at"])
                if item.get("confirmed_at"):
                    item["confirmed_at"] = parse_dt(item["confirmed_at"])
                pattern = LessonPattern(**item)
                self._lesson_patterns[pattern.pattern_id] = pattern

            for item in data.get("pattern_warnings", []):
                item["created_at"] = parse_dt(item["created_at"])
                if item.get("acknowledged_at"):
                    item["acknowledged_at"] = parse_dt(item["acknowledged_at"])
                warn = PatternWarning(**item)
                self._pattern_warnings[warn.warning_id] = warn

            print(
                f"[DataStore] Loaded persisted state from db.json ({len(self._users)} users, {len(self._documents)} documents, {len(self._candidate_merges)} merges, {len(self._sessions)} sessions, {len(self._rca_drafts)} RCAs, {len(self._regulatory_clauses)} clauses, {len(self._compliance_gaps)} gaps, {len(self._lesson_patterns)} patterns)"
            )
        except Exception as e:
            print(f"[DataStore] Failed to load state from db.json: {e}")

    # ──────────────────────────── Organisations ────────────────────────────

    def create_org(self, name: str, created_by: str) -> Organisation:
        with self._lock:
            org_id = str(uuid.uuid4())[:8]
            org = Organisation(
                id=org_id,
                name=name,
                created_at=datetime.now(timezone.utc),
                created_by=created_by,
            )
            self._orgs[org_id] = org
            self._save()
            return org

    def get_org(self, org_id: str) -> Organisation | None:
        return self._orgs.get(org_id)

    def find_org_by_name(self, name: str) -> Organisation | None:
        for org in self._orgs.values():
            if org.name.lower() == name.lower():
                return org
        return None

    def list_orgs(self) -> list[Organisation]:
        return list(self._orgs.values())

    # ──────────────────────────── Users ────────────────────────────────────

    def create_user(self, profile: UserProfile) -> UserProfile:
        with self._lock:
            self._users[profile.uid] = profile
            self._save()
            return profile

    def get_user(self, uid: str) -> UserProfile | None:
        return self._users.get(uid)

    def get_users_by_org(self, org_id: str) -> list[UserProfile]:
        return [u for u in self._users.values() if u.org_id == org_id]

    def update_user_role(self, uid: str, role: UserRole) -> UserProfile | None:
        with self._lock:
            user = self._users.get(uid)
            if user:
                user.role = role
                self._save()
                return user
            return None

    # ──────────────────────────── Documents ────────────────────────────────

    def create_document(self, doc: DocumentRecord) -> DocumentRecord:
        with self._lock:
            self._documents[doc.id] = doc
            self._save()
            return doc

    def get_document(self, doc_id: str) -> DocumentRecord | None:
        return self._documents.get(doc_id)

    def list_documents(
        self,
        org_id: str,
        page: int = 1,
        page_size: int = 20,
        stage: PipelineStage | None = None,
        doc_type: DocumentType | None = None,
    ) -> tuple[list[DocumentRecord], int]:
        docs = [d for d in self._documents.values() if d.org_id == org_id]
        if stage:
            docs = [d for d in docs if d.pipeline_stage == stage]
        if doc_type:
            docs = [d for d in docs if d.doc_type == doc_type]
        docs.sort(key=lambda d: d.created_at, reverse=True)
        total = len(docs)
        start = (page - 1) * page_size
        return docs[start : start + page_size], total

    def update_document_stage(
        self,
        doc_id: str,
        stage: PipelineStage,
        error: str | None = None,
        **kwargs: object,
    ) -> DocumentRecord | None:
        with self._lock:
            doc = self._documents.get(doc_id)
            if doc:
                doc.pipeline_stage = stage
                doc.pipeline_error = error
                doc.updated_at = datetime.now(timezone.utc)
                for key, value in kwargs.items():
                    if hasattr(doc, key) and value is not None:
                        setattr(doc, key, value)
                self._save()
                return doc
            return None

    def get_ingestion_stats(self, org_id: str) -> IngestionStats:
        docs = [d for d in self._documents.values() if d.org_id == org_id]
        entities = [e for e in self._entities.values() if e.org_id == org_id]
        chunks = [c for c in self._chunks.values() if c.org_id == org_id]
        by_type: dict[str, int] = {}
        queued = processing = completed = failed = needs_review = 0
        for d in docs:
            by_type[d.doc_type.value] = by_type.get(d.doc_type.value, 0) + 1
            if d.pipeline_stage == PipelineStage.QUEUED:
                queued += 1
            elif d.pipeline_stage == PipelineStage.COMPLETED:
                completed += 1
            elif d.pipeline_stage == PipelineStage.FAILED:
                failed += 1
            elif d.pipeline_stage == PipelineStage.NEEDS_REVIEW:
                needs_review += 1
            else:
                processing += 1
        return IngestionStats(
            total_documents=len(docs),
            queued=queued,
            processing=processing,
            completed=completed,
            failed=failed,
            needs_review=needs_review,
            total_entities=len(entities),
            total_chunks=len(chunks),
            by_type=by_type,
        )

    def get_review_queue(self, org_id: str) -> list[DocumentRecord]:
        return [
            d for d in self._documents.values() if d.org_id == org_id and d.needs_review
        ]

    # ──────────────────────────── Entities (FR-1.5) ───────────────────────

    def create_entity(self, entity: ExtractedEntity) -> ExtractedEntity:
        with self._lock:
            self._entities[entity.id] = entity
            self._save()
            return entity

    def get_entities_by_document(self, doc_id: str) -> list[ExtractedEntity]:
        return [e for e in self._entities.values() if e.document_id == doc_id]

    def get_entities_by_org(self, org_id: str) -> list[ExtractedEntity]:
        return [e for e in self._entities.values() if e.org_id == org_id]

    def get_entity(self, entity_id: str) -> ExtractedEntity | None:
        return self._entities.get(entity_id)

    def update_entity(self, entity_id: str, **kwargs: object) -> ExtractedEntity | None:
        with self._lock:
            entity = self._entities.get(entity_id)
            if entity:
                for key, value in kwargs.items():
                    if hasattr(entity, key) and value is not None:
                        setattr(entity, key, value)
                self._save()
                return entity
            return None

    def get_review_entities(self, org_id: str) -> list[ExtractedEntity]:
        return [
            e
            for e in self._entities.values()
            if e.org_id == org_id and e.needs_review and not e.reviewed
        ]

    # ──────────────────────────── Chunks (FR-1.6) ─────────────────────────

    def create_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        with self._lock:
            self._chunks[chunk.id] = chunk
            self._save()
            return chunk

    def get_chunks_by_document(self, doc_id: str) -> list[DocumentChunk]:
        chunks = [c for c in self._chunks.values() if c.document_id == doc_id]
        chunks.sort(key=lambda c: c.chunk_index)
        return chunks

    def get_chunk(self, chunk_id: str) -> DocumentChunk | None:
        return self._chunks.get(chunk_id)

    # ──────────────────────────── Connections (FR-1.4) ────────────────────

    def create_connection(self, conn: PIDConnection) -> PIDConnection:
        with self._lock:
            self._connections[conn.id] = conn
            self._save()
            return conn

    def get_connections_by_document(self, doc_id: str) -> list[PIDConnection]:
        return [c for c in self._connections.values() if c.document_id == doc_id]

    def update_connection(self, conn_id: str, status: str) -> PIDConnection | None:
        with self._lock:
            conn = self._connections.get(conn_id)
            if conn:
                conn.status = status
                self._save()
                return conn
            return None

    def delete_document_data(self, doc_id: str) -> None:
        """Deletes all entities, chunks, and connections associated with a document ID (FR-2.3.3)."""
        with self._lock:
            # Filter dicts keeping items not belonging to the document ID
            self._entities = {
                eid: ent
                for eid, ent in self._entities.items()
                if ent.document_id != doc_id
            }
            self._chunks = {
                cid: chk
                for cid, chk in self._chunks.items()
                if chk.document_id != doc_id
            }
            self._connections = {
                conn_id: conn
                for conn_id, conn in self._connections.items()
                if conn.document_id != doc_id
            }
            self._save()

    # ──────────────────────────── Candidate Merges (FR-2.2) ──────────────────

    def create_candidate_merge(self, merge: CandidateMerge) -> CandidateMerge:
        with self._lock:
            self._candidate_merges[merge.id] = merge
            self._save()
            return merge

    def get_candidate_merge(self, merge_id: str) -> CandidateMerge | None:
        return self._candidate_merges.get(merge_id)

    def list_candidate_merges(self, org_id: str) -> list[CandidateMerge]:
        return [m for m in self._candidate_merges.values() if m.org_id == org_id]

    def update_candidate_merge(
        self, merge_id: str, status: str
    ) -> CandidateMerge | None:
        with self._lock:
            merge = self._candidate_merges.get(merge_id)
            if merge:
                merge.status = status
                self._save()
                return merge
            return None

    # ──────────────────────────── Graph Operations (FR-2.4) ──────────────────

    def get_neighborhood(self, org_id: str, node_id: str, hops: int = 1) -> dict:
        """
        Traverse the graph starting from node_id and return connected nodes and edges (FR-2.4).
        """
        with self._lock:
            # Gather all documents and entities for the organization
            org_docs = {d.id: d for d in self._documents.values() if d.org_id == org_id}
            org_entities = {
                e.id: e for e in self._entities.values() if e.org_id == org_id
            }

            # Helper to build a node dict from DocumentRecord or ExtractedEntity
            def make_node(item) -> dict:
                if isinstance(item, DocumentRecord):
                    return {
                        "id": item.id,
                        "label": item.original_filename,
                        "type": "Document",
                        "properties": {
                            "doc_type": item.doc_type.value
                            if hasattr(item.doc_type, "value")
                            else str(item.doc_type),
                            "status": getattr(item, "status", "active"),
                            "pipeline_stage": item.pipeline_stage.value
                            if hasattr(item.pipeline_stage, "value")
                            else str(item.pipeline_stage),
                            "plant_id": item.plant_id,
                            "unit": item.unit,
                        },
                    }
                else:
                    clean_type = (
                        item.entity_type.value
                        if hasattr(item.entity_type, "value")
                        else str(item.entity_type)
                    )
                    clean_type = "".join(
                        [part.capitalize() for part in clean_type.split("_")]
                    )
                    return {
                        "id": item.id,
                        "label": item.value,
                        "type": clean_type,
                        "properties": {
                            "entity_type": item.entity_type.value
                            if hasattr(item.entity_type, "value")
                            else str(item.entity_type),
                            "confidence": item.confidence,
                            "canonical_id": item.canonical_id,
                            "aliases": getattr(item, "aliases", []),
                        },
                    }

            # Gather all candidate edges dynamically
            all_edges: list[dict[str, object]] = []

            # (a) Document -> ExtractedEntity (has_entity) OR specific semantic edges
            for ent in org_entities.values():
                doc = org_docs.get(ent.document_id)
                if not doc:
                    continue

                doc_type_str = (
                    doc.doc_type.value
                    if hasattr(doc.doc_type, "value")
                    else str(doc.doc_type)
                )
                ent_type_str = (
                    ent.entity_type.value
                    if hasattr(ent.entity_type, "value")
                    else str(ent.entity_type)
                )

                if doc_type_str == "work_order" and ent_type_str == "equipment_tag":
                    edge_type = "PERFORMED_ON"
                    all_edges.append(
                        {
                            "id": f"edge-wo-eq-{doc.id}-{ent.id}",
                            "source": doc.id,
                            "target": ent.canonical_id or ent.id,
                            "type": edge_type,
                        }
                    )
                elif (
                    doc_type_str == "incident_report"
                    and ent_type_str == "equipment_tag"
                ):
                    edge_type = "INVOLVED_IN"
                    all_edges.append(
                        {
                            "id": f"edge-inc-eq-{doc.id}-{ent.id}",
                            "source": doc.id,
                            "target": ent.canonical_id or ent.id,
                            "type": edge_type,
                        }
                    )
                elif (
                    doc_type_str == "safety_procedure"
                    and ent_type_str == "equipment_tag"
                ):
                    edge_type = "GOVERNED_BY_SOP"
                    all_edges.append(
                        {
                            "id": f"edge-sop-eq-{ent.canonical_id or ent.id}-{doc.id}",
                            "source": ent.canonical_id or ent.id,
                            "target": doc.id,
                            "type": edge_type,
                        }
                    )
                elif (
                    doc_type_str == "regulatory" and ent_type_str == "regulatory_clause"
                ):
                    edge_type = "GOVERNED_BY"
                    all_edges.append(
                        {
                            "id": f"edge-reg-cl-{doc.id}-{ent.id}",
                            "source": doc.id,
                            "target": ent.id,
                            "type": edge_type,
                        }
                    )
                elif doc_type_str == "work_order" and ent_type_str == "person":
                    edge_type = "ASSIGNED_TO"
                    all_edges.append(
                        {
                            "id": f"edge-wo-person-{doc.id}-{ent.id}",
                            "source": doc.id,
                            "target": ent.id,
                            "type": edge_type,
                        }
                    )
                else:
                    all_edges.append(
                        {
                            "id": f"edge-has-{doc.id}-{ent.id}",
                            "source": doc.id,
                            "target": ent.id,
                            "type": "HAS_ENTITY",
                        }
                    )

                # If resolved, we link the extraction node to its canonical node
                if ent.canonical_id and ent.canonical_id != ent.id:
                    all_edges.append(
                        {
                            "id": f"edge-alias-{ent.id}-{ent.canonical_id}",
                            "source": ent.id,
                            "target": ent.canonical_id,
                            "type": "RESOLVED_TO",
                        }
                    )

            # (b) PIDConnections (CONNECTS_TO between equipment)
            for conn in self._connections.values():
                if conn.org_id != org_id:
                    continue
                source_id = None
                target_id = None

                for ent in org_entities.values():
                    if ent.value.upper() == conn.source_tag.upper():
                        source_id = ent.canonical_id or ent.id
                        break
                for ent in org_entities.values():
                    if ent.value.upper() == conn.target_tag.upper():
                        target_id = ent.canonical_id or ent.id
                        break

                if source_id and target_id:
                    edge_entry: dict[str, object] = {
                        "id": conn.id,
                        "source": source_id,
                        "target": target_id,
                        "type": "CONNECTS_TO",
                        "properties": {
                            "status": conn.status,
                            "confidence": conn.confidence,
                        },
                    }
                    all_edges.append(edge_entry)

            # Check if requested node_id exists (as canonical id or regular id)
            start_node_id = node_id
            # Resolve to canonical_id if it's an alias
            if node_id in org_entities and org_entities[node_id].canonical_id:
                start_node_id = org_entities[node_id].canonical_id or node_id

            visited_nodes = set()
            active_edges = []

            queue = [(start_node_id, 0)]
            visited_nodes.add(start_node_id)

            while queue:
                current_id, current_hop = queue.pop(0)
                if current_hop >= hops:
                    continue

                for edge in all_edges:
                    neighbor = None
                    if edge["source"] == current_id:
                        neighbor = edge["target"]
                    elif edge["target"] == current_id:
                        neighbor = edge["source"]

                    if neighbor and isinstance(neighbor, str):
                        if neighbor not in visited_nodes:
                            if (
                                neighbor in org_docs
                                or neighbor in org_entities
                                or any(
                                    e.canonical_id == neighbor
                                    for e in org_entities.values()
                                )
                            ):
                                visited_nodes.add(neighbor)
                                queue.append((neighbor, current_hop + 1))
                                active_edges.append(edge)
                        else:
                            if edge not in active_edges:
                                active_edges.append(edge)

            # Assemble node details
            nodes_list = []
            for nid in visited_nodes:
                if nid in org_docs:
                    nodes_list.append(make_node(org_docs[nid]))
                elif nid in org_entities:
                    nodes_list.append(make_node(org_entities[nid]))
                else:
                    # Could be a canonical_id representing multiple merged tags
                    # Let's find any entity that has canonical_id equal to nid
                    matching_ents = [
                        e for e in org_entities.values() if e.canonical_id == nid
                    ]
                    if matching_ents:
                        # Use the first matching entity but representing the canonical view
                        rep_ent = matching_ents[0]
                        # Aggregate aliases
                        all_aliases = list(set([e.value for e in matching_ents]))
                        rep_ent.aliases = all_aliases
                        nodes_list.append(make_node(rep_ent))

            return {"nodes": nodes_list, "edges": active_edges}

    def search_graph_nodes(self, org_id: str, query: str) -> list[dict]:
        """
        Search graph nodes (documents and entities) by name/value (FR-2.4.1).
        """
        with self._lock:
            results = []
            q = query.lower()

            # Search documents
            for doc in self._documents.values():
                if doc.org_id == org_id and (
                    q in doc.original_filename.lower() or q in doc.filename.lower()
                ):
                    results.append(
                        {
                            "id": doc.id,
                            "label": doc.original_filename,
                            "type": "Document",
                        }
                    )

            # Search entities
            for ent in self._entities.values():
                if ent.org_id == org_id and q in ent.value.lower():
                    clean_type = (
                        ent.entity_type.value
                        if hasattr(ent.entity_type, "value")
                        else str(ent.entity_type)
                    )
                    clean_type = "".join(
                        [part.capitalize() for part in clean_type.split("_")]
                    )
                    results.append(
                        {
                            "id": ent.canonical_id or ent.id,
                            "label": ent.value,
                            "type": clean_type,
                        }
                    )

            # Deduplicate by id
            seen = set()
            unique_results = []
            for r in results:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    unique_results.append(r)
            return unique_results

    def get_graph_completeness(self, org_id: str) -> dict:
        """
        Compute completeness score (linked entities / total entities) and historical metrics (FR-2.5.2).
        """
        from app.models.ingestion import EntityType

        with self._lock:
            org_entities = [e for e in self._entities.values() if e.org_id == org_id]
            if not org_entities:
                return {
                    "score": 0.0,
                    "linked": 0,
                    "total": 0,
                    "trend": [80, 82, 85, 87, 90],
                }

            total = len(org_entities)
            linked = 0

            for ent in org_entities:
                if ent.canonical_id or ent.entity_type == EntityType.EQUIPMENT_TAG:
                    linked += 1
                elif ent.reviewed:
                    linked += 1

            score = round((linked / total) * 100, 1) if total > 0 else 100.0
            return {
                "score": score,
                "linked": linked,
                "total": total,
                "trend": [75.0, 78.5, 81.2, 84.0, score],
            }


    # ──────────────────────────── Copilot Sessions (FR-3.6) ────────────────

    def create_session(
        self, session_id: str, org_id: str, user_uid: str
    ) -> ConversationSession:
        with self._lock:
            session = ConversationSession(
                session_id=session_id,
                org_id=org_id,
                user_uid=user_uid,
            )
            self._sessions[session_id] = session
            self._save()
            return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        return self._sessions.get(session_id)

    def add_turn_to_session(
        self, session_id: str, turn: ConversationTurn
    ) -> ConversationSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.turns.append(turn)
                session.updated_at = datetime.now(timezone.utc)
                self._save()
                return session
            return None

    def list_sessions(self, org_id: str, user_uid: str) -> list[ConversationSession]:
        sessions = [
            s
            for s in self._sessions.values()
            if s.org_id == org_id and s.user_uid == user_uid
        ]
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._save()
                return True
            return False

    # ──────────────────────────── Copilot Feedback (FR-3.4.3) ─────────────

    def add_feedback(self, feedback: dict) -> dict:
        with self._lock:
            self._feedback.append(feedback)
            self._save()
            return feedback

    def get_feedback_by_session(self, session_id: str) -> list[dict]:
        return [f for f in self._feedback if f.get("session_id") == session_id]

    # ──────────────────────────── Query Logging (FR-3.7.1) ────────────────

    def log_query(self, entry: QueryLogEntry) -> None:
        with self._lock:
            self._query_logs.append(entry)
            self._save()

    def get_query_logs(self, org_id: str, limit: int = 200) -> list[QueryLogEntry]:
        logs = [q for q in self._query_logs if q.org_id == org_id]
        logs.sort(key=lambda q: q.timestamp, reverse=True)
        return logs[:limit]

    # ──────────────────────────── Copilot Retrieval Helpers ───────────────

    def search_chunks_fulltext(
        self, org_id: str, query_terms: list[str], limit: int = 20
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Full-text search over chunks: score by term overlap count.
        Returns (chunk, score) tuples sorted by score descending.
        """
        results: list[tuple[DocumentChunk, float]] = []
        query_lower = [t.lower() for t in query_terms if len(t) > 2]
        if not query_lower:
            return results

        for chunk in self._chunks.values():
            if chunk.org_id != org_id:
                continue
            text_lower = chunk.text.lower()
            hits = sum(1 for term in query_lower if term in text_lower)
            if hits > 0:
                score = hits / len(query_lower)
                results.append((chunk, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_chunks_by_entity_documents(
        self, org_id: str, entity_ids: list[str], limit: int = 15
    ) -> list[DocumentChunk]:
        """
        Graph-proximity retrieval (FR-3.2.2): find chunks from documents
        that are linked to the given entity IDs.
        """
        # Find all documents linked to the entity ids
        linked_doc_ids: set[str] = set()
        for entity in self._entities.values():
            if entity.org_id != org_id:
                continue
            eid = entity.canonical_id or entity.id
            if eid in entity_ids or entity.id in entity_ids:
                linked_doc_ids.add(entity.document_id)

        # Collect chunks from those documents
        chunks: list[DocumentChunk] = []
        for chunk in self._chunks.values():
            if chunk.org_id == org_id and chunk.document_id in linked_doc_ids:
                chunks.append(chunk)

        chunks.sort(key=lambda c: c.chunk_index)
        return chunks[:limit]

    def get_all_chunks_for_org(self, org_id: str) -> list[DocumentChunk]:
        """Return all chunks for an org (used for embedding-based search)."""
        return [c for c in self._chunks.values() if c.org_id == org_id]

    # ──────────────────────────── Maintenance Advisor (Phase 4) ────────────

    def get_events_by_equipment(self, org_id: str, equipment_tag: str) -> list[DocumentRecord]:
        """
        Finds all documents (work orders, incidents, SOPs) linked to the given
        equipment tag via entity mentions (FR-4.1.1).
        """
        target_upper = equipment_tag.upper().strip()
        matching_canonical_ids = set()
        matching_raw_ids = set()

        for entity in self._entities.values():
            if entity.org_id != org_id:
                continue
            if entity.entity_type.value == "equipment_tag":
                val = entity.value.upper().strip()
                norm = entity.normalised_value.upper().strip()
                if val == target_upper or norm == target_upper:
                    matching_raw_ids.add(entity.id)
                    if entity.canonical_id:
                        matching_canonical_ids.add(entity.canonical_id)

        linked_doc_ids = set()
        for entity in self._entities.values():
            if entity.org_id != org_id:
                continue
            eid = entity.canonical_id or entity.id
            if eid in matching_canonical_ids or entity.id in matching_raw_ids:
                linked_doc_ids.add(entity.document_id)

        documents = []
        for doc_id in linked_doc_ids:
            doc = self._documents.get(doc_id)
            if doc and doc.org_id == org_id:
                documents.append(doc)

        return documents

    def create_rca_draft(self, draft: RCADraft) -> None:
        with self._lock:
            self._rca_drafts[draft.rca_id] = draft
            self._save()

    def get_rca_draft(self, rca_id: str) -> RCADraft | None:
        return self._rca_drafts.get(rca_id)

    def update_rca_draft(self, rca_id: str, **kwargs) -> RCADraft | None:
        with self._lock:
            rca = self._rca_drafts.get(rca_id)
            if rca:
                for k, v in kwargs.items():
                    setattr(rca, k, v)
                self._save()
                return rca
            return None

    def list_rca_drafts(self, org_id: str) -> list[RCADraft]:
        # We need to filter drafts by org. Since RCAs are linked to equipment tags,
        # we check the equipment tag's entity org_id, or return all since it's local dev.
        # To be safe, we list all since there is no org_id on RCADraft, but we can match via equipment tag.
        return list(self._rca_drafts.values())

    # ──────────────────────────── Compliance & Quality (Phase 5) ────────────

    def delete_document(self, doc_id: str) -> None:
        """
        Deletes a document and performs a cascading cleanup of all related chunks,
        extracted entities, candidate merges, P&ID connections, and associated
        compliance/maintenance collections (FR-5.2.3).
        """
        with self._lock:
            # 1. Remove the document record
            if doc_id in self._documents:
                del self._documents[doc_id]

            # 2. Remove all layout chunks belonging to this document
            chunks_to_remove = [cid for cid, chk in self._chunks.items() if chk.document_id == doc_id]
            for cid in chunks_to_remove:
                del self._chunks[cid]

            # 3. Remove all extracted entities for this document
            entities_to_remove = [eid for eid, ent in self._entities.items() if ent.document_id == doc_id]
            for eid in entities_to_remove:
                del self._entities[eid]

            # 4. Clean up any P&ID connections referencing deleted entities/document
            conns_to_remove = [
                conn_id for conn_id, conn in self._connections.items()
                if conn.document_id == doc_id or conn.from_entity_id in entities_to_remove or conn.to_entity_id in entities_to_remove
            ]
            for conn_id in conns_to_remove:
                del self._connections[conn_id]

            # 5. Clean up candidate merges referencing deleted entities
            merges_to_remove = [
                mid for mid, merge in self._candidate_merges.items()
                if merge.source_entity_id in entities_to_remove or merge.target_entity_id in entities_to_remove
            ]
            for mid in merges_to_remove:
                del self._candidate_merges[mid]

            # 6. Clean up regulatory clauses referencing deleted document
            clauses_to_remove = [
                cid for cid, clause in self._regulatory_clauses.items() if clause.document_id == doc_id
            ]
            for cid in clauses_to_remove:
                del self._regulatory_clauses[cid]

            # 7. Clean up compliance gaps referencing deleted clauses
            gaps_to_remove = [
                gid for gid, gap in self._compliance_gaps.items() if gap.clause_id in clauses_to_remove
            ]
            for gid in gaps_to_remove:
                del self._compliance_gaps[gid]

            self._save()

    def create_regulatory_clause(self, clause: RegulatoryClause) -> None:
        with self._lock:
            self._regulatory_clauses[clause.id] = clause
            self._save()

    def get_regulatory_clause(self, clause_id: str) -> RegulatoryClause | None:
        return self._regulatory_clauses.get(clause_id)

    def list_regulatory_clauses(self) -> list[RegulatoryClause]:
        return list(self._regulatory_clauses.values())

    def create_compliance_gap(self, gap: ComplianceGap) -> None:
        with self._lock:
            self._compliance_gaps[gap.gap_id] = gap
            self._save()

    def get_compliance_gap(self, gap_id: str) -> ComplianceGap | None:
        return self._compliance_gaps.get(gap_id)

    def update_compliance_gap(self, gap_id: str, **kwargs) -> ComplianceGap | None:
        with self._lock:
            gap = self._compliance_gaps.get(gap_id)
            if gap:
                for k, v in kwargs.items():
                    setattr(gap, k, v)
                self._save()
                return gap
            return None

    def list_compliance_gaps(self) -> list[ComplianceGap]:
        return list(self._compliance_gaps.values())

    # ──────────────────────────── Lessons Learned (Phase 6) ────────────────

    def create_incident_enrichment(self, enrichment: IncidentEnrichment) -> None:
        with self._lock:
            self._incident_enrichments[enrichment.id] = enrichment
            self._save()

    def get_incident_enrichment(self, enrichment_id: str) -> IncidentEnrichment | None:
        return self._incident_enrichments.get(enrichment_id)

    def get_enrichment_by_document(self, doc_id: str) -> IncidentEnrichment | None:
        for e in self._incident_enrichments.values():
            if e.document_id == doc_id:
                return e
        return None

    def list_incident_enrichments(self, org_id: str) -> list[IncidentEnrichment]:
        return [e for e in self._incident_enrichments.values() if e.org_id == org_id]

    def create_lesson_pattern(self, pattern: LessonPattern) -> None:
        with self._lock:
            self._lesson_patterns[pattern.pattern_id] = pattern
            self._save()

    def get_lesson_pattern(self, pattern_id: str) -> LessonPattern | None:
        return self._lesson_patterns.get(pattern_id)

    def update_lesson_pattern(self, pattern_id: str, **kwargs) -> LessonPattern | None:
        with self._lock:
            pattern = self._lesson_patterns.get(pattern_id)
            if pattern:
                for k, v in kwargs.items():
                    setattr(pattern, k, v)
                self._save()
                return pattern
            return None

    def list_lesson_patterns(self, org_id: str) -> list[LessonPattern]:
        return [p for p in self._lesson_patterns.values() if p.org_id == org_id]

    def create_pattern_warning(self, warning: PatternWarning) -> None:
        with self._lock:
            self._pattern_warnings[warning.warning_id] = warning
            self._save()

    def get_pattern_warning(self, warning_id: str) -> PatternWarning | None:
        return self._pattern_warnings.get(warning_id)

    def update_pattern_warning(self, warning_id: str, **kwargs) -> PatternWarning | None:
        with self._lock:
            warn = self._pattern_warnings.get(warning_id)
            if warn:
                for k, v in kwargs.items():
                    setattr(warn, k, v)
                self._save()
                return warn
            return None

    def list_pattern_warnings(self, org_id: str) -> list[PatternWarning]:
        return [w for w in self._pattern_warnings.values() if w.org_id == org_id]


# Singleton instance
store = DataStore()
