"""
UnifyOps  -  Lessons Learned & Failure Intelligence Service (Phase 6)

Implements:
- FR-6.1: Incident enrichment (structured extraction of severity, conditions, equipment)
- FR-6.2: Cross-incident pattern detection agent
- FR-6.3: Proactive warning push on confirmed pattern triggers
- FR-6.4: Pattern search & repository
"""

import uuid
from collections import Counter
from datetime import datetime, timezone

from app.core.store import store
from app.models.ingestion import DocumentType, PipelineStage
from app.models.lessons import (
    IncidentEnrichment,
    IncidentSeverity,
    LessonPattern,
    PatternStatus,
    PatternWarning,
    WarningStatus,
)


class LessonsLearnedService:
    """Service for incident enrichment, pattern detection, and proactive warnings."""

    # ──────────────────────── FR-6.1: Incident Enrichment ────────────────────────

    def enrich_incident_document(self, org_id: str, document_id: str) -> IncidentEnrichment | None:
        """
        Parse an incident/near-miss document for structured fields.
        Uses text analysis to extract severity, contributing conditions,
        affected equipment, and immediate actions taken.
        """
        # Skip if already enriched
        existing = store.get_enrichment_by_document(document_id)
        if existing:
            return existing

        doc = store.get_document(document_id)
        if not doc or doc.doc_type != DocumentType.INCIDENT_REPORT:
            return None

        # Get raw text from chunks
        chunks = [c for c in store._chunks.values() if c.document_id == document_id]
        if not chunks:
            return None

        raw_text = " ".join(c.text for c in chunks).lower()

        # Extract severity using keyword matching
        severity = self._classify_severity(raw_text)

        # Extract contributing conditions using keyword patterns
        conditions = self._extract_conditions(raw_text)

        # Extract affected equipment from entity resolution
        equipment_entities = [
            e for e in store._entities.values()
            if e.document_id == document_id and e.entity_type.value == "equipment_tag"
        ]
        affected_equipment = list(set(e.value.upper() for e in equipment_entities))

        # Extract immediate actions
        actions = self._extract_actions(raw_text)

        # Extract location
        location = self._extract_location(raw_text, doc)

        enrichment = IncidentEnrichment(
            id=f"enrich-{uuid.uuid4().hex[:8]}",
            document_id=document_id,
            org_id=org_id,
            severity=severity,
            severity_confidence=0.85,
            contributing_conditions=conditions,
            affected_equipment=affected_equipment,
            immediate_actions_taken=actions,
            location=location,
            incident_date=doc.created_at.strftime("%Y-%m-%d"),
        )

        store.create_incident_enrichment(enrichment)
        return enrichment

    def _classify_severity(self, text: str) -> IncidentSeverity:
        """Classify incident severity from document text using keyword matching."""
        text_lower = text.lower()

        # Major indicators
        major_keywords = ["fatality", "fatal", "explosion", "catastrophic", "critical injury",
                          "hospitalization", "environmental release", "major spill"]
        if any(k in text_lower for k in major_keywords):
            return IncidentSeverity.MAJOR

        # Serious indicators
        serious_keywords = ["serious injury", "fire", "equipment failure", "shutdown",
                            "unplanned outage", "leak", "significant damage", "structural failure"]
        if any(k in text_lower for k in serious_keywords):
            return IncidentSeverity.SERIOUS

        # Near-miss indicators
        near_miss_keywords = ["near miss", "near-miss", "close call", "potential",
                              "could have", "averted", "narrowly"]
        if any(k in text_lower for k in near_miss_keywords):
            return IncidentSeverity.NEAR_MISS

        return IncidentSeverity.MINOR

    def _extract_conditions(self, text: str) -> list[str]:
        """Extract contributing conditions from incident text."""
        conditions = []
        condition_patterns = {
            "inadequate_maintenance": ["maintenance overdue", "deferred maintenance", "delayed repair",
                                       "worn", "corroded", "degraded", "aging"],
            "procedural_violation": ["violated", "not followed", "bypassed", "skipped",
                                     "without authorization", "ignored sop", "deviation from"],
            "training_gap": ["untrained", "unfamiliar", "first time", "inadequate training",
                             "no certification", "inexperienced"],
            "equipment_design": ["design flaw", "design limitation", "not rated for",
                                 "incorrect specification", "undersized"],
            "environmental": ["weather", "temperature", "humidity", "corrosive environment",
                              "high pressure", "extreme heat"],
            "communication_failure": ["miscommunication", "not communicated", "handover failure",
                                       "shift change", "unclear instructions"],
            "human_error": ["operator error", "human error", "mistakenly", "accidentally",
                            "incorrect operation", "wrong valve"],
        }

        text_lower = text.lower()
        for condition, keywords in condition_patterns.items():
            if any(k in text_lower for k in keywords):
                conditions.append(condition.replace("_", " ").title())

        # Always ensure at least one condition for demo
        if not conditions:
            conditions.append("Under Investigation")

        return conditions

    def _extract_actions(self, text: str) -> str:
        """Extract immediate actions taken from incident text."""
        action_indicators = ["action taken", "corrective action", "immediately",
                             "shut down", "isolated", "replaced", "repaired",
                             "emergency response", "evacuated"]
        text_lower = text.lower()
        for indicator in action_indicators:
            if indicator in text_lower:
                idx = text_lower.index(indicator)
                # Get surrounding sentence context (approx 200 chars)
                start = max(0, idx - 50)
                end = min(len(text), idx + 200)
                snippet = text[start:end].strip()
                # Clean and return the first match
                return snippet.replace("\n", " ").strip()
        return "Immediate actions not explicitly documented"

    def _extract_location(self, text: str, doc) -> str:
        """Extract incident location."""
        if doc.unit:
            return doc.unit
        if doc.plant_id:
            return doc.plant_id
        # Try to find location in text
        location_patterns = ["unit", "area", "section", "plant", "zone", "block"]
        text_lower = text.lower()
        for pattern in location_patterns:
            if pattern in text_lower:
                idx = text_lower.index(pattern)
                snippet = text[idx:idx + 30].strip()
                return snippet.split("\n")[0].strip()
        return "Unspecified"

    # ──────────────────────── FR-6.2: Pattern Detection ────────────────────────

    def detect_patterns(self, org_id: str) -> list[LessonPattern]:
        """
        Analyse enriched incidents to find cross-incident patterns.
        Clusters by shared contributing conditions and equipment type.
        Returns newly created candidate patterns.
        """
        enrichments = store.list_incident_enrichments(org_id)
        if len(enrichments) < 2:
            return []

        new_patterns: list[LessonPattern] = []
        existing_patterns = store.list_lesson_patterns(org_id)
        existing_incident_sets = set()
        for p in existing_patterns:
            existing_incident_sets.add(frozenset(p.contributing_incident_ids))

        # Strategy 1: Cluster by shared contributing conditions
        condition_to_incidents: dict[str, list[IncidentEnrichment]] = {}
        for enrich in enrichments:
            for cond in enrich.contributing_conditions:
                condition_to_incidents.setdefault(cond, []).append(enrich)

        for condition, incidents in condition_to_incidents.items():
            if len(incidents) < 2:
                continue
            if condition == "Under Investigation":
                continue

            incident_ids = sorted([e.document_id for e in incidents])
            if frozenset(incident_ids) in existing_incident_sets:
                continue

            # Gather all equipment across the cluster
            all_equipment = []
            for e in incidents:
                all_equipment.extend(e.affected_equipment)
            equipment_tags = list(set(all_equipment))

            # Determine severity from worst incident in cluster
            severity_order = {
                IncidentSeverity.NEAR_MISS: 0,
                IncidentSeverity.MINOR: 1,
                IncidentSeverity.SERIOUS: 2,
                IncidentSeverity.MAJOR: 3,
            }
            worst_severity = max(incidents, key=lambda e: severity_order.get(e.severity, 0)).severity

            pattern = LessonPattern(
                pattern_id=f"pattern-{uuid.uuid4().hex[:8]}",
                org_id=org_id,
                shared_factor=f"Recurring '{condition}' condition detected across {len(incidents)} incidents",
                trigger_condition=f"New work order or inspection involving: {condition}",
                contributing_incident_ids=incident_ids,
                contributing_equipment_tags=equipment_tags,
                status=PatternStatus.CANDIDATE,
                severity=worst_severity,
                evidence_summary=(
                    f"{len(incidents)} incidents share the contributing condition '{condition}'. "
                    f"Affected equipment: {', '.join(equipment_tags) if equipment_tags else 'various'}. "
                    f"This pattern suggests a systemic issue that individual reviews may miss."
                ),
            )
            store.create_lesson_pattern(pattern)
            new_patterns.append(pattern)
            existing_incident_sets.add(frozenset(incident_ids))

        # Strategy 2: Cluster by shared equipment with multiple incidents
        equip_to_incidents: dict[str, list[IncidentEnrichment]] = {}
        for enrich in enrichments:
            for eq in enrich.affected_equipment:
                equip_to_incidents.setdefault(eq, []).append(enrich)

        for equipment, incidents in equip_to_incidents.items():
            if len(incidents) < 2:
                continue

            incident_ids = sorted([e.document_id for e in incidents])
            if frozenset(incident_ids) in existing_incident_sets:
                continue

            # Gather all conditions across incidents for this equipment
            all_conditions = []
            for e in incidents:
                all_conditions.extend(e.contributing_conditions)
            common_conditions = [c for c, cnt in Counter(all_conditions).items() if cnt >= 2]

            worst_severity = max(
                incidents,
                key=lambda e: {IncidentSeverity.NEAR_MISS: 0, IncidentSeverity.MINOR: 1,
                               IncidentSeverity.SERIOUS: 2, IncidentSeverity.MAJOR: 3}.get(e.severity, 0)
            ).severity

            pattern = LessonPattern(
                pattern_id=f"pattern-{uuid.uuid4().hex[:8]}",
                org_id=org_id,
                shared_factor=f"Equipment '{equipment}' involved in {len(incidents)} incidents",
                trigger_condition=f"New work order or permit involving equipment {equipment}",
                contributing_incident_ids=incident_ids,
                contributing_equipment_tags=[equipment],
                status=PatternStatus.CANDIDATE,
                severity=worst_severity,
                evidence_summary=(
                    f"Equipment {equipment} has been involved in {len(incidents)} separate incidents. "
                    f"Common conditions: {', '.join(common_conditions) if common_conditions else 'varied'}. "
                    f"This recurring involvement suggests the equipment may need design review or enhanced procedures."
                ),
            )
            store.create_lesson_pattern(pattern)
            new_patterns.append(pattern)
            existing_incident_sets.add(frozenset(incident_ids))

        return new_patterns

    # ──────────────────────── FR-6.3: Proactive Warnings ────────────────────────

    def check_trigger_warnings(self, org_id: str, new_doc_id: str | None = None) -> list[PatternWarning]:
        """
        Check confirmed patterns against recent activity and generate warnings.
        Called when new documents are ingested or on-demand.
        """
        confirmed_patterns = [
            p for p in store.list_lesson_patterns(org_id)
            if p.status == PatternStatus.CONFIRMED
        ]
        if not confirmed_patterns:
            return []

        new_warnings: list[PatternWarning] = []

        # Get recent documents (last ingested or specific doc)
        if new_doc_id:
            docs = [store.get_document(new_doc_id)]
            docs = [d for d in docs if d is not None]
        else:
            all_docs, _ = store.list_documents(org_id=org_id, page_size=10)
            docs = [d for d in all_docs if d.doc_type in (DocumentType.WORK_ORDER, DocumentType.INCIDENT_REPORT)]

        for pattern in confirmed_patterns:
            for doc in docs:
                # Check if document's equipment tags match pattern's equipment tags
                doc_entities = [
                    e for e in store._entities.values()
                    if e.document_id == doc.id and e.entity_type.value == "equipment_tag"
                ]
                doc_equipment = set(e.value.upper() for e in doc_entities)
                pattern_equipment = set(t.upper() for t in pattern.contributing_equipment_tags)

                overlap = doc_equipment & pattern_equipment
                if not overlap:
                    continue

                # Check for duplicate warnings (same pattern + same document)
                existing_warnings = store.list_pattern_warnings(org_id)
                already_warned = any(
                    w.pattern_id == pattern.pattern_id and w.triggered_by_doc_id == doc.id
                    for w in existing_warnings
                )
                if already_warned:
                    continue

                # Check if the triggering document is one of the contributing incidents (skip self-referral)
                if doc.id in pattern.contributing_incident_ids:
                    continue

                warning = PatternWarning(
                    warning_id=f"warn-{uuid.uuid4().hex[:8]}",
                    pattern_id=pattern.pattern_id,
                    org_id=org_id,
                    triggered_by_doc_id=doc.id,
                    target_equipment_tag=", ".join(overlap),
                    message=(
                        f"Pattern Alert: '{pattern.shared_factor}'  -  "
                        f"A confirmed failure pattern involving {', '.join(overlap)} has been triggered by "
                        f"document '{doc.original_filename}'. "
                        f"Review the pattern evidence before proceeding."
                    ),
                    status=WarningStatus.PENDING,
                )
                store.create_pattern_warning(warning)
                new_warnings.append(warning)

        return new_warnings

    # ──────────────────────── FR-6.4: Pattern Search ────────────────────────

    def search_patterns(self, org_id: str, query: str) -> list[LessonPattern]:
        """Full-text search across confirmed lesson patterns."""
        patterns = store.list_lesson_patterns(org_id)
        q = query.lower()

        results = []
        for p in patterns:
            searchable = f"{p.shared_factor} {p.trigger_condition} {p.evidence_summary}".lower()
            searchable += " ".join(p.contributing_equipment_tags).lower()
            if q in searchable:
                results.append(p)

        return results

    # ──────────────────────── Dashboard Stats ────────────────────────

    def get_dashboard_stats(self, org_id: str) -> dict:
        """Aggregated stats for the Lessons Learned frontend dashboard."""
        patterns = store.list_lesson_patterns(org_id)
        warnings = store.list_pattern_warnings(org_id)
        enrichments = store.list_incident_enrichments(org_id)

        candidate_count = sum(1 for p in patterns if p.status == PatternStatus.CANDIDATE)
        confirmed_count = sum(1 for p in patterns if p.status == PatternStatus.CONFIRMED)
        dismissed_count = sum(1 for p in patterns if p.status == PatternStatus.DISMISSED)

        pending_warnings = sum(1 for w in warnings if w.status == WarningStatus.PENDING)
        total_warnings = len(warnings)

        return {
            "total_patterns": len(patterns),
            "candidate_patterns": candidate_count,
            "confirmed_patterns": confirmed_count,
            "dismissed_patterns": dismissed_count,
            "total_warnings": total_warnings,
            "pending_warnings": pending_warnings,
            "enriched_incidents": len(enrichments),
        }


# Singleton instance
lessons_service = LessonsLearnedService()
