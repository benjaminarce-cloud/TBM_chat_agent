import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Event, Session


async def check_daily_thresholds() -> bool:
    settings = get_settings()
    if not settings.admin_alert_email:
        return False
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    async with SessionLocal() as db:
        sessions = await db.scalar(
            select(func.count())
            .select_from(Session)
            .where(Session.started_at >= start, Session.started_at < end)
        )
        spend = await db.scalar(
            select(
                func.coalesce(func.sum(Event.payload["estimated_cost_usd"].as_float()), 0.0)
            ).where(Event.type == "llm_usage", Event.ts >= start, Event.ts < end)
        )
    reasons = []
    if (
        settings.daily_session_alert_threshold is not None
        and sessions >= settings.daily_session_alert_threshold
    ):
        reasons.append(f"sessions: {sessions} (threshold {settings.daily_session_alert_threshold})")
    if (
        settings.daily_spend_alert_usd is not None
        and float(spend) >= settings.daily_spend_alert_usd
    ):
        reasons.append(
            f"estimated Claude spend: {float(spend):.2f} USD (threshold {settings.daily_spend_alert_usd:.2f})"
        )
    if not reasons:
        return False
    if not settings.resend_api_key or not settings.handoff_from_email:
        raise RuntimeError("Resend is not configured for the daily alert")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.handoff_from_email,
                "to": [settings.admin_alert_email],
                "subject": "TBM chat pilot daily threshold alert",
                "text": "The pilot crossed a configured threshold:\n- " + "\n- ".join(reasons),
            },
        )
        response.raise_for_status()
    return True


if __name__ == "__main__":
    print(asyncio.run(check_daily_thresholds()))
