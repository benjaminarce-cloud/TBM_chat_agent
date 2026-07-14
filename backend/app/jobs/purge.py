import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, update

from app.db import SessionLocal
from app.models import Consent, Event, Lead, Message, RateLimitBucket, Session


async def purge_expired_data(retention_days: int = 90) -> int:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=retention_days)
    captured = (
        select(Lead.id)
        .where(
            Lead.session_id == Session.id,
            or_(Lead.email.is_not(None), Lead.phone.is_not(None)),
            Lead.lane_origin_city.is_not(None),
            Lead.lane_dest_city.is_not(None),
        )
        .exists()
    )
    disqualified = (
        select(Lead.id).where(Lead.session_id == Session.id, Lead.status == "disqualified").exists()
    )
    async with SessionLocal() as db:
        # Token-bucket keys contain salted IP hashes; they do not need long-term retention.
        await db.execute(
            delete(RateLimitBucket).where(RateLimitBucket.updated_at < now - timedelta(days=7))
        )
        session_ids = list(
            (
                await db.scalars(
                    select(Session.id).where(
                        Session.started_at < cutoff,
                        or_(~captured, disqualified),
                    )
                )
            ).all()
        )
        if not session_ids:
            await db.commit()
            return 0
        await db.execute(delete(Message).where(Message.session_id.in_(session_ids)))
        await db.execute(delete(Lead).where(Lead.session_id.in_(session_ids)))
        await db.execute(delete(Consent).where(Consent.session_id.in_(session_ids)))
        await db.execute(
            update(Session).where(Session.id.in_(session_ids)).values(source=None, status="ended")
        )
        db.add_all(
            [
                Event(
                    session_id=session_id, type="purged", payload={"retention_days": retention_days}
                )
                for session_id in session_ids
            ]
        )
        await db.commit()
        return len(session_ids)


if __name__ == "__main__":
    print(asyncio.run(purge_expired_data()))
