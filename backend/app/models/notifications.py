"""
UnifyOps — Notification Models (Phase 7.2)

Models for user notification preference centre and user notification records.
"""

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class NotificationCategory(str, Enum):
    COMPLIANCE_GAP = "compliance_gap"
    MAINTENANCE_ATTENTION = "maintenance_attention"
    SAFETY_WARNING = "safety_warning"


class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"


class NotificationFrequency(str, Enum):
    REAL_TIME = "real_time"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"
    DISABLED = "disabled"


class PreferenceItem(BaseModel):
    category: NotificationCategory
    in_app: bool = True
    email: bool = False
    sms: bool = False
    frequency: NotificationFrequency = NotificationFrequency.REAL_TIME


class NotificationPreference(BaseModel):
    user_uid: str
    org_id: str
    preferences: list[PreferenceItem] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationRecord(BaseModel):
    id: str
    user_uid: str
    org_id: str
    category: NotificationCategory
    title: str
    message: str
    channel: NotificationChannel
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
