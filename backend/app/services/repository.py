import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import phonenumbers
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Consent, Event, Lead, Message, Session


@dataclass
class LeadUpsertResult:
    lead: Lead | None
    consented: bool
    newly_captured: bool
    changed_fields: list[str]


def lead_is_captured(lead: Lead | None) -> bool:
    return bool(
        lead and (lead.email or lead.phone) and lead.lane_origin_city and lead.lane_dest_city
    )


def qualification_score(lead: Lead) -> int:
    score = 0
    if lead.email or lead.phone:
        score += 30
    if lead.lane_origin_city and lead.lane_dest_city:
        score += 30
    if lead.freight_type:
        score += 10
    if lead.volume_amount and lead.volume_period:
        score += 10
    if lead.target_ship_date and lead.target_ship_date <= date.today() + timedelta(days=30):
        score += 10
    if lead.cross_border:
        score += 10
    return score


def normalize_phone(value: str, language: str | None = None) -> str | None:
    try:
        region = "MX" if language == "es" else "US"
        parsed = phonenumbers.parse(value, None if value.strip().startswith("+") else region)
        if not phonenumbers.is_possible_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None


async def active_consent(
    db: AsyncSession, session_id: uuid.UUID, notice_version: str
) -> Consent | None:
    return await db.scalar(
        select(Consent)
        .where(
            Consent.session_id == session_id,
            Consent.notice_version == notice_version,
            Consent.cross_border_ack.is_(True),
        )
        .order_by(Consent.ts.desc())
        .limit(1)
    )


async def record_event(
    db: AsyncSession, session_id: uuid.UUID, event_type: str, payload: dict | None = None
) -> Event:
    event = Event(session_id=session_id, type=event_type, payload=payload)
    db.add(event)
    return event


async def get_history(db: AsyncSession, session_id: uuid.UUID, limit: int = 12) -> list[dict]:
    rows = list(
        (
            await db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.ts.desc())
                .limit(limit)
            )
        ).all()
    )
    rows.reverse()
    return [{"role": row.role, "content": row.content[:4000]} for row in rows]


async def upsert_lead_fields(
    db: AsyncSession, session_id: uuid.UUID, extracted: dict, notice_version: str
) -> LeadUpsertResult:
    """The consent check is intentionally inside the write boundary, not only in the API."""
    consent = await active_consent(db, session_id, notice_version)
    if consent is None or not extracted:
        return LeadUpsertResult(
            None, consented=consent is not None, newly_captured=False, changed_fields=[]
        )

    lead = await db.scalar(
        select(Lead).where(Lead.session_id == session_id).order_by(Lead.created_at).limit(1)
    )
    if lead is None:
        lead = Lead(session_id=session_id, consent_id=consent.id)
        db.add(lead)
    before = lead_is_captured(lead)
    changed: list[str] = []
    language = extracted.get("language") or lead.language
    for key, value in extracted.items():
        if value is None or not hasattr(lead, key):
            continue
        if isinstance(value, str):
            value = value.strip()[:2000]
        if key == "phone":
            value = normalize_phone(str(value), language)
            if value is None:
                continue
        if key in {"lane_origin_country", "lane_dest_country"} and isinstance(value, str):
            value = value.upper()[:2]
        if getattr(lead, key) != value:
            setattr(lead, key, value)
            changed.append(key)
    lead.consent_id = consent.id
    lead.updated_at = datetime.now(UTC)
    lead.qualification_score = qualification_score(lead)
    await db.flush()
    after = lead_is_captured(lead)

    for field in changed:
        await record_event(db, session_id, "field_captured", {"field": field})
    if after and not before:
        await record_event(db, session_id, "lead_captured", {"lead_id": str(lead.id)})
    return LeadUpsertResult(
        lead, consented=True, newly_captured=after and not before, changed_fields=changed
    )


async def persist_message_if_consented(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str,
    notice_version: str,
    latency_ms: int | None = None,
) -> bool:
    """Persist no transcript at all pre-consent, which is stricter than PII pattern guessing."""
    consented = await active_consent(db, session_id, notice_version) is not None
    if consented:
        db.add(
            Message(
                session_id=session_id,
                role=role,
                content=content,
                latency_ms=latency_ms,
            )
        )
    # Content-free message telemetry is safe before consent and keeps engagement metrics valid.
    payload = {"role": role, "persisted": consented}
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    await record_event(db, session_id, "message", payload)
    return consented


async def lock_session(db: AsyncSession, session_id: uuid.UUID) -> Session | None:
    return await db.scalar(select(Session).where(Session.id == session_id).with_for_update())
