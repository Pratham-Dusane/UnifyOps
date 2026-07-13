"""
UnifyOps - Auth Router

User registration, profile management, and organisation management.
Firebase handles authentication; this router manages the extended profile
(org membership, role, department) that Firebase doesn't store natively.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header

from app.core.config import settings
from app.core.store import store
from app.models.auth import (
    Organisation,
    OrganisationCreate,
    UserProfile,
    UserProfileResponse,
    UserRegister,
    UserRole,
)
from app.models.common import HealthResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Auth & Organisation"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="auth-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


# ──────────────────────────── Registration ────────────────────────────────


@router.post("/register", response_model=UserProfileResponse)
async def register_user(
    body: UserRegister,
    x_user_uid: str = Header(..., description="Firebase UID from client"),
    x_user_email: str = Header(..., description="Firebase email from client"),
) -> UserProfileResponse:
    """
    Register a new user profile after Firebase sign-up.

    If org_id is provided, the user joins that org.
    Otherwise, if an org with org_name exists, the user joins it.
    Otherwise, a new org is created and the user becomes its admin.
    """
    # Check if user already registered
    existing = store.get_user(x_user_uid)
    if existing:
        existing_org = store.get_org(existing.org_id)
        return UserProfileResponse(
            uid=existing.uid,
            email=existing.email,
            display_name=existing.display_name,
            org_id=existing.org_id,
            org_name=existing_org.name if existing_org else "",
            role=existing.role.value,
            department=existing.department,
            plant_id=existing.plant_id,
        )

    # Resolve organisation
    org: Organisation | None = None
    role = UserRole.VIEWER
    if body.org_id:
        org = store.get_org(body.org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")
    else:
        org = store.find_org_by_name(body.org_name)
        if not org:
            # Create new org - first user becomes admin
            org = store.create_org(name=body.org_name, created_by=x_user_uid)
            role = UserRole.PLATFORM_ADMIN

    # Create user profile
    profile = UserProfile(
        uid=x_user_uid,
        email=x_user_email,
        display_name=body.display_name,
        org_id=org.id,
        role=role,
        department=body.department,
        created_at=datetime.now(timezone.utc),
    )
    store.create_user(profile)

    return UserProfileResponse(
        uid=profile.uid,
        email=profile.email,
        display_name=profile.display_name,
        org_id=profile.org_id,
        org_name=org.name,
        role=profile.role.value,
        department=profile.department,
        plant_id=profile.plant_id,
    )


# ──────────────────────────── Profile ─────────────────────────────────────


@router.get("/profile", response_model=UserProfileResponse | None)
async def get_profile(
    x_user_uid: str = Header(..., description="Firebase UID from client"),
) -> UserProfileResponse | None:
    """Get the current user's profile. Returns null if not yet registered."""
    user = store.get_user(x_user_uid)
    if not user:
        return None
    org = store.get_org(user.org_id)
    return UserProfileResponse(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        org_id=user.org_id,
        org_name=org.name if org else "",
        role=user.role.value,
        department=user.department,
        plant_id=user.plant_id,
    )


# ──────────────────────────── Organisations ───────────────────────────────


@router.get("/organisations", response_model=list[Organisation])
async def list_organisations() -> list[Organisation]:
    """List all organisations (for join-org picker during registration)."""
    return store.list_orgs()


@router.post("/organisations", response_model=Organisation)
async def create_organisation(
    body: OrganisationCreate,
    x_user_uid: str = Header(..., description="Firebase UID"),
) -> Organisation:
    """Create a new organisation."""
    existing = store.find_org_by_name(body.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Organisation '{body.name}' already exists",
        )
    return store.create_org(name=body.name, created_by=x_user_uid)


@router.get("/organisations/{org_id}/users", response_model=list[UserProfileResponse])
async def list_org_users(org_id: str) -> list[UserProfileResponse]:
    """List all users in an organisation."""
    org = store.get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    users = store.get_users_by_org(org_id)
    return [
        UserProfileResponse(
            uid=u.uid,
            email=u.email,
            display_name=u.display_name,
            org_id=u.org_id,
            org_name=org.name,
            role=u.role.value,
            department=u.department,
            plant_id=u.plant_id,
        )
        for u in users
    ]
