import html
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Event, Lead
from app.services.repository import record_event


def _lead_summary(lead: Lead) -> str:
    fields = [
        ("Name", lead.name),
        ("Company", lead.company),
        ("Email", lead.email),
        ("Phone", lead.phone),
        ("Preferred contact", lead.preferred_contact),
        ("Language", lead.language),
        (
            "Origin",
            ", ".join(
                filter(
                    None, [lead.lane_origin_city, lead.lane_origin_state, lead.lane_origin_country]
                )
            ),
        ),
        (
            "Destination",
            ", ".join(
                filter(None, [lead.lane_dest_city, lead.lane_dest_state, lead.lane_dest_country])
            ),
        ),
        ("Freight", lead.freight_type),
        ("Equipment", lead.equipment),
        (
            "Volume",
            " ".join(
                filter(
                    None,
                    [str(lead.volume_amount) if lead.volume_amount else None, lead.volume_period],
                )
            ),
        ),
        ("Target ship date", str(lead.target_ship_date) if lead.target_ship_date else None),
        (
            "Cross-border",
            "Yes" if lead.cross_border else "No" if lead.cross_border is False else None,
        ),
        (
            "Qualification score",
            str(lead.qualification_score) if lead.qualification_score is not None else None,
        ),
        ("Notes", lead.notes),
    ]
    return "".join(
        f"<tr><th align='left' style='padding:6px 12px 6px 0'>{html.escape(label)}</th>"
        f"<td style='padding:6px 0'>{html.escape(value)}</td></tr>"
        for label, value in fields
        if value
    )


async def send_handoff_if_needed(
    db: AsyncSession, session_id: uuid.UUID, lead: Lead, settings: Settings
) -> bool:
    already_sent = await db.scalar(
        select(Event.id)
        .where(Event.session_id == session_id, Event.type == "handoff_sent")
        .limit(1)
    )
    if already_sent:
        return True
    if not all([settings.resend_api_key, settings.handoff_from_email, settings.handoff_to_email]):
        await record_event(
            db,
            session_id,
            "handoff_pending_config",
            {"reason": "Resend sender or recipient is not configured"},
        )
        return False

    payload = {
        "from": settings.handoff_from_email,
        "to": [settings.handoff_to_email],
        "subject": f"New TBM website freight lead: {lead.lane_origin_city} to {lead.lane_dest_city}",
        "html": (
            "<h2>New captured freight lead</h2><table>"
            f"{_lead_summary(lead)}</table><p>Session: {html.escape(str(session_id))}</p>"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
            )
            response.raise_for_status()
        await record_event(db, session_id, "handoff_sent", {"provider": "resend"})
        return True
    except httpx.HTTPError as exc:
        await record_event(
            db, session_id, "handoff_failed", {"provider": "resend", "error": type(exc).__name__}
        )
        return False
