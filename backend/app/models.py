import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

JsonType = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locale: Mapped[str] = mapped_column(String, default="es")
    kb_version: Mapped[str | None] = mapped_column(String)
    source: Mapped[dict | None] = mapped_column(JsonType)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="active")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class Consent(Base):
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint("cross_border_ack = true", name="consents_ack_required"),
        UniqueConstraint("session_id", "notice_version", name="uq_consents_session_notice"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sessions.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notice_version: Mapped[str] = mapped_column(String)
    locale: Mapped[str] = mapped_column(String)
    cross_border_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_hash: Mapped[str | None] = mapped_column(String)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sessions.id"), index=True)
    consent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("consents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    status: Mapped[str] = mapped_column(String, default="new")
    name: Mapped[str | None] = mapped_column(String)
    company: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    preferred_contact: Mapped[str | None] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String)
    lane_origin_city: Mapped[str | None] = mapped_column(String)
    lane_origin_state: Mapped[str | None] = mapped_column(String)
    lane_origin_country: Mapped[str | None] = mapped_column(String)
    lane_dest_city: Mapped[str | None] = mapped_column(String)
    lane_dest_state: Mapped[str | None] = mapped_column(String)
    lane_dest_country: Mapped[str | None] = mapped_column(String)
    freight_type: Mapped[str | None] = mapped_column(String)
    equipment: Mapped[str | None] = mapped_column(String)
    volume_amount: Mapped[int | None] = mapped_column(Integer)
    volume_period: Mapped[str | None] = mapped_column(String)
    target_ship_date: Mapped[date | None] = mapped_column(Date)
    cross_border: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    qualification_score: Mapped[int | None] = mapped_column(Integer)


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True)
    title_en: Mapped[str | None] = mapped_column(String)
    title_es: Mapped[str | None] = mapped_column(String)
    body_md: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="draft")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sessions.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict | None] = mapped_column(JsonType)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    tokens: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
