"""
Main UnifyOps SDK Client Entrypoint.
"""

from typing import Optional
from unifyops.compliance import ComplianceEngine
from unifyops.copilot import CopilotEngine
from unifyops.document_ai import DocumentProcessor
from unifyops.exceptions import AuthenticationError
from unifyops.lessons import LessonsEngine
from unifyops.maintenance import MaintenanceEngine
from unifyops.models import Document, DocumentType
from unifyops.store import KnowledgeStore


class UnifyOpsClient:
    """
    Main entrypoint for interacting with the UnifyOps AI Industrial Knowledge Intelligence Platform SDK.

    Usage:
        client = UnifyOpsClient(org_id="org-plant-1", api_key="my-key")
        doc = client.ingest_document("SOP contents...", filename="SOP_P204.pdf", document_type=DocumentType.SOP)
        response = client.copilot.query("What is the maintenance SOP for P-204?")
    """

    def __init__(self, org_id: str = "default_org", api_key: Optional[str] = None) -> None:
        if api_key and api_key.strip() == "invalid":
            raise AuthenticationError("Invalid API key provided.")

        self.org_id = org_id
        self.api_key = api_key

        self.store = KnowledgeStore()
        self.document_ai = DocumentProcessor(self.store)
        self.copilot = CopilotEngine(self.store)
        self.maintenance = MaintenanceEngine(self.store)
        self.compliance = ComplianceEngine(self.store)
        self.lessons = LessonsEngine(self.store)

    def ingest_document(
        self,
        text: str,
        filename: str,
        document_type: DocumentType = DocumentType.OTHER,
        plant_id: Optional[str] = None,
        department: Optional[str] = None,
    ) -> Document:
        """
        Ingest text document into the knowledge graph store.
        """
        return self.document_ai.process_text(
            text=text,
            filename=filename,
            org_id=self.org_id,
            document_type=document_type,
            plant_id=plant_id,
            department=department,
        )

    def clear_store(self) -> None:
        """Clear all in-memory graph nodes, documents, and chunks."""
        self.store.clear()
