"""Pydantic schemas for WhatsApp notifications and webhooks."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class NotificationLogRead(BaseModel):
    id: UUID
    tenant_id: UUID
    branch_id: UUID | None = None
    event_type: str
    entity_id: str
    student_id: UUID | None = None
    student_name: str | None = None
    student_number: str | None = None
    section_name: str | None = None
    recipient_phone: str | None = None
    template_name: str
    idempotency_key: str
    provider_message_id: str | None = None
    delivery_status: str
    error_message: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DispatchProgressResponse(BaseModel):
    entity_id: str
    status: str # PUBLISHED, IN_PROGRESS, DRAFT
    total_notifications: int
    completed_notifications: int
    failed_notifications: int
    missing_phone_notifications: int
    progress_percentage: float
    is_ongoing: bool


class MetaWebhookStatusItem(BaseModel):
    id: str
    status: str # sent, delivered, read, failed
    timestamp: str
    recipient_id: str | None = None


class MetaWebhookChangeValue(BaseModel):
    messaging_product: str | None = "whatsapp"
    statuses: list[MetaWebhookStatusItem] = []


class MetaWebhookChange(BaseModel):
    value: MetaWebhookChangeValue
    field: str | None = "messages"


class MetaWebhookEntry(BaseModel):
    id: str | None = None
    changes: list[MetaWebhookChange] = []


class MetaWebhookPayload(BaseModel):
    object: str | None = "whatsapp_business_account"
    entry: list[MetaWebhookEntry] = []
