"""
UnifyOps SDK - AI Industrial Knowledge Intelligence Platform Python Library.
"""

__version__ = "0.1.0"

from unifyops.client import UnifyOpsClient
from unifyops.compliance import ComplianceEngine
from unifyops.copilot import CopilotEngine
from unifyops.document_ai import DocumentProcessor
from unifyops.exceptions import (
    AuthenticationError,
    EntityNotFoundError,
    QueryExecutionError,
    StorageError,
    UnifyOpsError,
    ValidationError,
)
from unifyops.lessons import LessonsEngine
from unifyops.maintenance import MaintenanceEngine
from unifyops.models import (
    Citation,
    ComplianceGap,
    ComplianceScanRequest,
    ComplianceScanResult,
    ConversationTurn,
    CopilotQuery,
    CopilotResponse,
    Document,
    DocumentChunk,
    DocumentType,
    EntityCategory,
    EntityNode,
    KnowledgeRelationship,
    LessonLearned,
    RCARequest,
    RCAResult,
    StarterPrompt,
)
from unifyops.store import KnowledgeStore

__all__ = [
    "__version__",
    "UnifyOpsClient",
    "KnowledgeStore",
    "DocumentProcessor",
    "CopilotEngine",
    "MaintenanceEngine",
    "ComplianceEngine",
    "LessonsEngine",
    "Document",
    "DocumentChunk",
    "DocumentType",
    "EntityNode",
    "EntityCategory",
    "KnowledgeRelationship",
    "Citation",
    "ConversationTurn",
    "CopilotQuery",
    "CopilotResponse",
    "StarterPrompt",
    "RCARequest",
    "RCAResult",
    "ComplianceGap",
    "ComplianceScanRequest",
    "ComplianceScanResult",
    "LessonLearned",
    "UnifyOpsError",
    "AuthenticationError",
    "EntityNotFoundError",
    "QueryExecutionError",
    "ValidationError",
    "StorageError",
]
