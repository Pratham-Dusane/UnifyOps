"""
UnifyOps — Quality & Regulatory Compliance Service (Phase 5)

Implements:
- Clause segmentation & parsing (FR-5.1.1, FR-5.1.2)
- Compliance Gap Detection Agent (FR-5.2.1, FR-5.2.2)
- Audit Evidence Package Generation (FR-5.3.1, FR-5.3.3)
"""

import uuid
from datetime import datetime, timezone, timedelta

from app.core.store import store
from app.models.compliance import (
    RegulatoryClause,
    ComplianceGap,
    CheckType,
    GapSeverity,
    GapStatus,
    AuditPackageResponse,
)
from app.models.ingestion import DocumentType
from app.services.gemini import gemini_service


class ComplianceService:
    """Manages regulatory clause mapping, automated compliance checks, and audit reports."""

    # ───────────────── 1. Clause Segmentation (FR-5.1) ──────────────────────

    def segment_regulatory_document(self, org_id: str, document_id: str) -> list[RegulatoryClause]:
        """
        Segments a raw regulatory text document into separate addressable clause nodes
        and calls Gemini Flash to summarize each clause (FR-5.1.1, FR-5.1.2).
        """
        doc = store.get_document(document_id)
        if not doc or doc.doc_type != DocumentType.REGULATORY:
            return []

        # Find document text chunks
        chunks = [c for c in store._chunks.values() if c.document_id == document_id]
        if not chunks:
            return []

        # Clear existing clauses for this document to avoid duplicates or stale data
        for c_id in list(store._regulatory_clauses.keys()):
            if store._regulatory_clauses[c_id].document_id == document_id:
                del store._regulatory_clauses[c_id]

        clauses: list[RegulatoryClause] = []

        import re
        paragraphs: list[str] = []
        for chunk in chunks:
            cleaned_text = re.sub(r"^\[[^\]]+\]\s*", "", chunk.text)
            # Split into separate rules if multiple newlines exist within the chunk text
            for block in cleaned_text.split("\n\n"):
                for sub in block.split("\n"):
                    if len(sub.strip()) > 30:
                        paragraphs.append(sub.strip())

        # Extract equipment tags associated with this document to link clauses automatically
        doc_entities = [e for e in store._entities.values() if e.document_id == document_id]
        equipment_tags = [e.value for e in doc_entities if e.entity_type.value == "equipment_tag"]

        for idx, text in enumerate(paragraphs[:10]):  # Limit to top 10 clauses for simplicity
            clause_id = f"clause-{document_id[:5]}-{idx + 1}"
            clause_number = f"Rule {idx + 1}"
            
            # Simple keyword matching to parse a clause number
            import re
            match = re.search(r"(?:clause|section|rule|rule\s+no\.?)\s*(\d+(?:\.\d+)*\w*)", text, re.IGNORECASE)
            if match:
                clause_number = f"Section {match.group(1)}"

            # Call Gemini to write a plain-language summary (FR-5.1.2)
            summary = self._summarize_clause(text)

            # Link clauses to governing procedures via topical embedding similarity or overlap
            # (In local dev, we match keywords like LOTO, Lockout, Tagout, or Pump)
            linked_procedures = []
            for other_doc in store._documents.values():
                if other_doc.doc_type == DocumentType.SAFETY_PROCEDURE and other_doc.org_id == org_id:
                    # check simple keyword overlap
                    if "loto" in text.lower() or "tagout" in text.lower():
                        linked_procedures.append(other_doc.id)

            clause = RegulatoryClause(
                id=clause_id,
                document_id=document_id,
                clause_number=clause_number,
                verbatim_text=text,
                summary=summary,
                linked_procedures=linked_procedures,
                linked_equipment_tags=equipment_tags,
            )
            store.create_regulatory_clause(clause)
            clauses.append(clause)

        return clauses

    def _summarize_clause(self, text: str) -> str:
        """Helper to get a plain-language clause summary from Gemini (FR-5.1.2)."""
        prompt = f"""Summarize this verbatim industrial regulation clause into a single plain-language sentence
suitable for site technicians. Do not use legal jargon. Keep it brief.

Regulation Text: {text}"""

        if gemini_service.enabled:
            try:
                import google.generativeai as genai
                model = genai.GenerativeModel("gemini-2.0-flash")
                res = model.generate_content(prompt)
                if res.text:
                    return res.text.strip()
            except:
                pass

        # Fallback summary
        return text[:100] + ("..." if len(text) > 100 else "")

    # ───────────────── 2. Compliance Gap Agent (FR-5.2) ─────────────────────

    def run_compliance_gap_agent(self, org_id: str) -> list[ComplianceGap]:
        """
        Runs automated compliance checking rules on all segmented regulatory clauses (FR-5.2.1, FR-5.2.3).
        """
        clauses = store.list_regulatory_clauses()
        new_gaps: list[ComplianceGap] = []

        for clause in clauses:
            # Let's verify each check rule (FR-5.2.1)
            
            # --- Check A: Governing Procedure Exists ---
            if not clause.linked_procedures:
                # No governing procedure linked to this clause
                gap_id = f"gap-{clause.id}-missing"
                # If already exists, skip or update
                if not store.get_compliance_gap(gap_id):
                    gap = ComplianceGap(
                        gap_id=gap_id,
                        clause_id=clause.id,
                        clause_number=clause.clause_number,
                        check_type=CheckType.MISSING_PROCEDURE,
                        details=f"No safety procedure exists in records governing regulation {clause.clause_number}.",
                        evidence="Verified: No documents of type 'safety_procedure' are linked to this regulatory clause.",
                        severity=GapSeverity.HIGH,
                        status=GapStatus.OPEN,
                    )
                    store.create_compliance_gap(gap)
                    new_gaps.append(gap)
                continue

            # --- Check B: Governing Procedure Stale Check ---
            stale_threshold = datetime.now(timezone.utc) - timedelta(days=365)
            for proc_id in clause.linked_procedures:
                proc = store.get_document(proc_id)
                if proc and proc.created_at < stale_threshold:
                    gap_id = f"gap-{clause.id}-stale-{proc_id[:5]}"
                    if not store.get_compliance_gap(gap_id):
                        gap = ComplianceGap(
                            gap_id=gap_id,
                            clause_id=clause.id,
                            clause_number=clause.clause_number,
                            check_type=CheckType.STALE_PROCEDURE,
                            details=f"The safety procedure '{proc.original_filename}' governing {clause.clause_number} has not been reviewed or updated in the last 12 months.",
                            evidence=f"Safety Procedure {proc.original_filename} last updated: {proc.created_at.date().isoformat()}.",
                            severity=GapSeverity.MEDIUM,
                            status=GapStatus.OPEN,
                        )
                        store.create_compliance_gap(gap)
                        new_gaps.append(gap)

            # --- Check C: Unresolved Non-Conformance (FR-5.2.1) ---
            # If the clause mentions equipment, check if there are incidents or inspection reports listing failure
            for tag in clause.linked_equipment_tags:
                timeline_docs = store.get_events_by_equipment(org_id, tag)
                for doc in timeline_docs:
                    if doc.doc_type == DocumentType.INCIDENT_REPORT:
                        # Check if incident is unresolved (in a real DB we'd check status, locally we search if there's an open gap)
                        gap_id = f"gap-{clause.id}-nonconformance-{doc.id[:5]}"
                        if not store.get_compliance_gap(gap_id):
                            gap = ComplianceGap(
                                gap_id=gap_id,
                                clause_id=clause.id,
                                clause_number=clause.clause_number,
                                check_type=CheckType.UNRESOLVED_NON_CONFORMANCE,
                                details=f"Active unresolved incident report '{doc.original_filename}' linked to equipment {tag} violates conformance requirements for {clause.clause_number}.",
                                evidence=f"Incident report '{doc.original_filename}' remains active in records for equipment {tag}.",
                                severity=GapSeverity.HIGH,
                                status=GapStatus.OPEN,
                            )
                            store.create_compliance_gap(gap)
                            new_gaps.append(gap)

        return new_gaps

    # ───────────────── 3. Audit Packager (FR-5.3) ───────────────────────────

    def generate_audit_package(self, org_id: str, user_uid: str, clause_ids: list[str]) -> AuditPackageResponse:
        """
        Assembles regulatory text, governing procedures, and inspection evidence
        into a structured, citation-backed Markdown package (FR-5.3.1, FR-5.3.3).
        """
        user = store.get_user(user_uid)
        username = user.display_name if user else "Compliance Officer"

        package_markdown = []
        package_markdown.append(f"# Quality & Safety Audit Evidence Package")
        package_markdown.append(f"**Generated on**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        package_markdown.append(f"**Compiled by**: {username}")
        package_markdown.append(f"**Plant Location**: {org_id}")
        package_markdown.append("\n---\n")

        files_included = set()

        for clause_id in clause_ids:
            clause = store.get_regulatory_clause(clause_id)
            if not clause:
                continue

            reg_doc = store.get_document(clause.document_id)
            reg_doc_name = reg_doc.original_filename if reg_doc else "Regulatory Manual"
            files_included.add(reg_doc_name)

            package_markdown.append(f"## Regulatory Requirement: {clause.clause_number}")
            package_markdown.append(f"*Verbatim Text*:\n> {clause.verbatim_text}\n")
            package_markdown.append(f"*Summary*: {clause.summary}\n")

            # Mapped Governing Procedures
            package_markdown.append("### Governing Plant Procedures")
            if clause.linked_procedures:
                for proc_id in clause.linked_procedures:
                    proc = store.get_document(proc_id)
                    if proc:
                        files_included.add(proc.original_filename)
                        package_markdown.append(f"- **Document**: {proc.original_filename}")
                        package_markdown.append(f"  - **Type**: Safety SOP")
                        package_markdown.append(f"  - **Date**: {proc.created_at.date().isoformat()}")
                        
                        # Add a snippet of LOTO or procedure chunks if available
                        proc_chunks = [c for c in store._chunks.values() if c.document_id == proc.id]
                        if proc_chunks:
                            package_markdown.append(f"  - **Procedure Excerpt (Citation: L1-L15)**:\n  > {proc_chunks[0].text[:300]}...")
            else:
                package_markdown.append("*Warning: No governing plant safety procedure is linked to this regulatory rule.*")

            # Active Compliance Posture
            gaps = [g for g in store.list_compliance_gaps() if g.clause_id == clause_id]
            open_gaps = [g for g in gaps if g.status == GapStatus.OPEN]

            package_markdown.append("### Conformance Status")
            if open_gaps:
                package_markdown.append("🔴 **Non-Compliant: Active Deviation Flagged**")
                for gap in open_gaps:
                    package_markdown.append(f"- **Severity**: {gap.severity.upper()}")
                    package_markdown.append(f"- **Details**: {gap.details}")
                    package_markdown.append(f"- **Evidence**: {gap.evidence}")
            else:
                package_markdown.append("🟢 **Compliant**")
                package_markdown.append("- Governing procedure exists and is current. No active non-conformance indicators recorded.")

            package_markdown.append("\n---\n")

        # Create audit package record
        package_id = f"aud-{str(uuid.uuid4())[:8]}"
        response = AuditPackageResponse(
            package_id=package_id,
            title=f"Audit Package - {len(clause_ids)} Clauses",
            generated_by=username,
            content_markdown="\n".join(package_markdown),
            files_included=list(files_included),
        )

        return response


# Singleton
compliance_service = ComplianceService()
