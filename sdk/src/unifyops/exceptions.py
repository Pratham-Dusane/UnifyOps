"""
Custom exceptions for the UnifyOps SDK.
"""

class UnifyOpsError(Exception):
    """Base exception for all UnifyOps SDK errors."""
    pass


class AuthenticationError(UnifyOpsError):
    """Raised when API key or authorization fails."""
    pass


class EntityNotFoundError(UnifyOpsError):
    """Raised when a requested entity or document is not found."""
    pass


class QueryExecutionError(UnifyOpsError):
    """Raised when query execution or RAG synthesis fails."""
    pass


class ValidationError(UnifyOpsError):
    """Raised when request payload validation fails."""
    pass


class StorageError(UnifyOpsError):
    """Raised when document/graph storage operations fail."""
    pass
