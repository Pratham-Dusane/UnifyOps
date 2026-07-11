"""
UnifyOps — Shared Pydantic Models

Common response/request models used across all service routers.
"""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Standard health check response for every service."""

    service: str = Field(description="Name of the service")
    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(description="Application version")
    environment: str = Field(description="Current environment (dev/staging/prod)")


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(description="Human-readable error message")
    request_id: str | None = Field(
        default=None, description="Correlation ID for debugging"
    )


class MessageResponse(BaseModel):
    """Generic message response for placeholder endpoints."""

    message: str
    service: str
    phase: str = Field(description="PRD phase this feature belongs to")
