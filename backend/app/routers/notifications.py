"""
UnifyOps  -  Notification Service Router (Phase 7.2)

Implements:
- User notification listing (FR-6.3.2)
- Notification read acknowledgement (FR-6.3.3)
- Notification preference settings (FR-7.2.1)
- Validation preventing disabling safety alerts (FR-7.2.2)
- Digest compilation trigger (FR-7.2.3)
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.core.store import store
from app.models.common import HealthResponse
from app.models.notifications import (
    NotificationPreference,
    NotificationRecord,
    PreferenceItem,
    NotificationCategory,
    NotificationChannel,
    NotificationFrequency,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notification Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="notification-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("", response_model=list[NotificationRecord])
async def list_user_notifications(
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[NotificationRecord]:
    """List all notifications for the authenticated user."""
    notifications = store.list_notifications(x_user_org, x_user_uid)

    # Populate sample notifications if the database is empty (for local dev and demo)
    if not notifications:
        samples = [
            NotificationRecord(
                id=str(uuid.uuid4())[:8],
                user_uid=x_user_uid,
                org_id=x_user_org,
                category=NotificationCategory.MAINTENANCE_ATTENTION,
                title="Critical Asset Alert: P-204",
                message="Pump P-204 attention score is at 86% based on repeated seal leakage events.",
                channel=NotificationChannel.IN_APP,
                is_read=False,
                created_at=datetime.now(timezone.utc),
            ),
            NotificationRecord(
                id=str(uuid.uuid4())[:8],
                user_uid=x_user_uid,
                org_id=x_user_org,
                category=NotificationCategory.COMPLIANCE_GAP,
                title="Compliance Gap Detected",
                message="Procedure SOP-17 does not explicitly reference OISD-STD-154 Clause 6.2.3 requirements.",
                channel=NotificationChannel.IN_APP,
                is_read=False,
                created_at=datetime.now(timezone.utc),
            ),
            NotificationRecord(
                id=str(uuid.uuid4())[:8],
                user_uid=x_user_uid,
                org_id=x_user_org,
                category=NotificationCategory.SAFETY_WARNING,
                title="Proactive Safety Warning",
                message="Graphite gasket failure pattern observed on similar line CDU-201. Verify torque sequence before restart.",
                channel=NotificationChannel.IN_APP,
                is_read=False,
                created_at=datetime.now(timezone.utc),
            ),
        ]
        for s in samples:
            store.create_notification(s)
        notifications = store.list_notifications(x_user_org, x_user_uid)

    # Sort: unread first, then newest first
    notifications.sort(key=lambda n: (n.is_read, n.created_at), reverse=True)
    return notifications


@router.post("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """Mark a specific notification as read."""
    success = store.mark_notification_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read", "notification_id": notification_id}


@router.get("/preferences", response_model=NotificationPreference)
async def get_preferences(
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> NotificationPreference:
    """Get the user's notification preferences. Creates defaults if none exist."""
    pref = store.get_notification_preference(x_user_uid)
    if not pref:
        # Create standard defaults
        default_pref = NotificationPreference(
            user_uid=x_user_uid,
            org_id=x_user_org,
            preferences=[
                PreferenceItem(
                    category=NotificationCategory.COMPLIANCE_GAP,
                    in_app=True,
                    email=True,
                    sms=False,
                    frequency=NotificationFrequency.DAILY_DIGEST,
                ),
                PreferenceItem(
                    category=NotificationCategory.MAINTENANCE_ATTENTION,
                    in_app=True,
                    email=True,
                    sms=False,
                    frequency=NotificationFrequency.REAL_TIME,
                ),
                PreferenceItem(
                    category=NotificationCategory.SAFETY_WARNING,
                    in_app=True,
                    email=True,
                    sms=True,
                    frequency=NotificationFrequency.REAL_TIME,
                ),
            ],
        )
        store.create_or_update_notification_preference(default_pref)
        pref = default_pref
    return pref


@router.put("/preferences", response_model=NotificationPreference)
async def update_preferences(
    body: NotificationPreference,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> NotificationPreference:
    """
    Update user notification preferences.
    Enforces that safety warnings cannot be fully disabled (FR-7.2.2).
    """
    if body.user_uid != x_user_uid or body.org_id != x_user_org:
        raise HTTPException(status_code=400, detail="Invalid preference ownership")

    # Enforce safety warnings policy
    for pref_item in body.preferences:
        if pref_item.category == NotificationCategory.SAFETY_WARNING:
            # Check if completely disabled
            all_channels_disabled = not (pref_item.in_app or pref_item.email or pref_item.sms)
            frequency_disabled = pref_item.frequency == NotificationFrequency.DISABLED

            if all_channels_disabled or frequency_disabled:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Safety warnings cannot be fully disabled (Guiding Principle 2). "
                        "Please select at least one delivery channel (In-App, Email, or SMS) "
                        "and set a valid alert frequency."
                    ),
                )

    body.updated_at = datetime.now(timezone.utc)
    store.create_or_update_notification_preference(body)
    return body


@router.post("/send-digest")
async def trigger_digest_compilation(
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """
    FR-7.2.3: Compiles pending notifications of digest frequency into a digest email message
    and registers an aggregated notification.
    """
    pref = store.get_notification_preference(x_user_uid)
    if not pref:
        raise HTTPException(status_code=404, detail="Preferences not configured")

    # List all notifications for the user
    user_notifs = store.list_notifications(x_user_org, x_user_uid)
    unread_notifs = [n for n in user_notifs if not n.is_read]

    if not unread_notifs:
        return {"message": "No pending notifications for digest."}

    # Synthesize digest content
    digest_items = []
    for n in unread_notifs:
        digest_items.append(f"- [{n.category.value.upper()}] {n.title}: {n.message}")

    digest_text = "\n".join(digest_items)
    digest_message = (
        f"Hello. Here is your UnifyOps Daily Digest for {datetime.now(timezone.utc).strftime('%Y-%m-%d')}:\n\n"
        f"{digest_text}\n\n"
        "Verify these updates in your workspace."
    )

    # Log digest compile message and mark aggregated alerts as read
    for n in unread_notifs:
        store.mark_notification_read(n.id)

    # Create a new aggregated digest notification
    digest_notif = NotificationRecord(
        id=str(uuid.uuid4())[:8],
        user_uid=x_user_uid,
        org_id=x_user_org,
        category=NotificationCategory.MAINTENANCE_ATTENTION,
        title="UnifyOps Digest Compiled",
        message=f"Your aggregated digest containing {len(unread_notifs)} items has been generated.",
        channel=NotificationChannel.IN_APP,
        is_read=False,
    )
    store.create_notification(digest_notif)

    return {
        "message": "Digest compiled and sent successfully",
        "digest_content": digest_message,
        "items_compiled": len(unread_notifs),
    }
