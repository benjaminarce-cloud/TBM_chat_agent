import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourcePayload(BaseModel):
    page: str | None = Field(default=None, max_length=500)
    referrer: str | None = Field(default=None, max_length=500)
    utm: dict[str, str] | None = None
    user_agent: str | None = Field(default=None, max_length=500)


class SessionCreate(BaseModel):
    locale: Literal["es", "en"] = "es"
    parent_origin: str = Field(max_length=300)
    source: SourcePayload | None = None


class SessionCreated(BaseModel):
    session_id: uuid.UUID
    widget_token: str


class ConsentCreate(BaseModel):
    notice_version: str = Field(min_length=1, max_length=80)
    locale: Literal["es", "en"]
    cross_border_ack: bool


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be blank")
        return value


class FeedbackCreate(BaseModel):
    thumbs: Literal["up", "down"]


class LeadExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    preferred_contact: Literal["email", "phone", "whatsapp"] | None = None
    language: Literal["es", "en"] | None = None
    lane_origin_city: str | None = None
    lane_origin_state: str | None = None
    lane_origin_country: str | None = None
    lane_dest_city: str | None = None
    lane_dest_state: str | None = None
    lane_dest_country: str | None = None
    freight_type: str | None = None
    equipment: Literal["dry_van", "reefer", "flatbed", "other", "unknown"] | None = None
    volume_amount: int | None = Field(default=None, ge=0)
    volume_period: Literal["one_time", "weekly", "monthly", "unknown"] | None = None
    target_ship_date: date | None = None
    cross_border: bool | None = None
    notes: str | None = None


class TurnAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["quote_request", "question", "pricing_ask", "human_request", "off_topic"]
    escalate: bool
    escalate_reason: str | None = None
    extracted: dict = Field(default_factory=dict)

    @field_validator("extracted")
    @classmethod
    def validate_extracted_fields(cls, value: dict) -> dict:
        return LeadExtraction.model_validate(value).model_dump(exclude_none=True, mode="json")
