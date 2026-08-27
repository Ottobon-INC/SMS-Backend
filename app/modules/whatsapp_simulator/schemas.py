"""Pydantic schemas for WhatsApp Simulator."""

from typing import Any
from pydantic import BaseModel, Field


class OutboundComponentParameter(BaseModel):
    type: str = "text"
    text: str | None = None


class OutboundComponent(BaseModel):
    type: str = "body"
    parameters: list[OutboundComponentParameter | str | Any] = Field(default_factory=list)


class OutboundTemplatePayload(BaseModel):
    name: str
    language: dict[str, Any] | None = None
    components: list[OutboundComponent] = Field(default_factory=list)


class OutboundTextMessage(BaseModel):
    body: str = ""


class MetaOutboundPayload(BaseModel):
    messaging_product: str | None = "whatsapp"
    to: str | None = "+919876543210"
    type: str = "template"
    template: OutboundTemplatePayload | None = None
    text: OutboundTextMessage | None = None


class SimulatorMessageObject(BaseModel):
    id: str
    timestamp: str
    toPhone: str
    type: str
    templateName: str
    header: str
    category: str
    body: str
