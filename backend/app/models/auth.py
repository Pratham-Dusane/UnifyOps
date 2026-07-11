"""
UnifyOps — Auth Models

User profile, organisation, and role management models.
Implements PRD Section 3.5 role-based access scoping and multi-org tenancy.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """PRD Section 4 — Persona-mapped roles."""

    FIELD_TECHNICIAN = "field_technician"        # Rajesh
    MAINTENANCE_ENGINEER = "maintenance_engineer" # Priya
    COMPLIANCE_OFFICER = "compliance_officer"      # Anita
    SENIOR_ENGINEER = "senior_engineer"            # Vikram
    PLATFORM_ADMIN = "platform_admin"              # Deepak
    PLANT_HEAD = "plant_head"                      # Mr. Iyer
    VIEWER = "viewer"                              # Read-only default


class Organisation(BaseModel):
    """An organisation (plant/company) in the system."""

    id: str = Field(description="Unique organisation ID")
    name: str = Field(description="Organisation display name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(description="UID of the user who created the org")


class OrganisationCreate(BaseModel):
    """Request model for creating a new organisation."""

    name: str = Field(min_length=2, max_length=100, description="Organisation name")


class UserProfile(BaseModel):
    """Extended user profile stored in the backend (beyond Firebase auth)."""

    uid: str = Field(description="Firebase UID")
    email: str
    display_name: str = Field(default="")
    org_id: str = Field(description="Organisation the user belongs to")
    role: UserRole = Field(default=UserRole.VIEWER)
    department: str = Field(default="")
    plant_id: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserRegister(BaseModel):
    """Request model for registering a new user profile after Firebase sign-up."""

    display_name: str = Field(min_length=1, max_length=100)
    org_name: str = Field(
        min_length=2,
        max_length=100,
        description="Organisation name — creates new if not found",
    )
    org_id: str | None = Field(
        default=None,
        description="Existing org ID to join (if provided, org_name is ignored)",
    )
    department: str = Field(default="")


class UserProfileResponse(BaseModel):
    """User profile returned to the client."""

    uid: str
    email: str
    display_name: str
    org_id: str
    org_name: str
    role: str
    department: str
    plant_id: str
