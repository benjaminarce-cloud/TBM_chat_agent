import json
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
@pytest.mark.asyncio
async def test_all_analytics_views_return_sane_seeded_values() -> None:
    engine = create_async_engine(DATABASE_URL or "")
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            session_id = await connection.scalar(
                text("INSERT INTO sessions (locale) VALUES ('en') RETURNING id")
            )
            events = [
                ("message", {"role": "user", "persisted": True}),
                ("first_token", {"latency_ms": 120}),
                ("message", {"role": "assistant", "persisted": True, "latency_ms": 480}),
                ("escalated", {"reason": "pricing_ask"}),
                ("feedback", {"thumbs": "up"}),
            ]
            for event_type, payload in events:
                await connection.execute(
                    text(
                        "INSERT INTO events (session_id, type, payload) "
                        "VALUES (:session_id, :type, CAST(:payload AS jsonb))"
                    ),
                    {
                        "session_id": session_id,
                        "type": event_type,
                        "payload": json.dumps(payload),
                    },
                )
            await connection.execute(
                text(
                    "INSERT INTO leads "
                    "(session_id, status, email, lane_origin_city, lane_dest_city) "
                    "VALUES (:session_id, 'qualified', 'lead@example.com', 'Laredo', 'Monterrey')"
                ),
                {"session_id": session_id},
            )

            engagement = (
                (await connection.execute(text("SELECT * FROM analytics_engagement")))
                .mappings()
                .one()
            )
            capture = (
                (await connection.execute(text("SELECT * FROM analytics_lead_capture")))
                .mappings()
                .one()
            )
            qualified = (
                (await connection.execute(text("SELECT * FROM analytics_qualified_leads")))
                .mappings()
                .one()
            )
            escalation = (
                (await connection.execute(text("SELECT * FROM analytics_escalation")))
                .mappings()
                .one()
            )
            latency = (
                (await connection.execute(text("SELECT * FROM analytics_latency"))).mappings().one()
            )
            feedback = (
                (await connection.execute(text("SELECT * FROM analytics_feedback")))
                .mappings()
                .one()
            )

            assert engagement["engaged_sessions"] >= 1
            assert 0 <= engagement["engagement_rate"] <= 1
            assert capture["captured_leads"] >= 1
            assert 0 <= capture["lead_capture_rate"] <= 1
            assert qualified["qualified_leads"] >= 1
            assert 0 <= qualified["qualified_lead_rate"] <= 1
            assert escalation["escalated_sessions"] >= 1
            assert 0 <= escalation["escalation_rate"] <= 1
            assert float(latency["median_first_token_ms"]) > 0
            assert float(latency["median_full_response_ms"]) > 0
            assert feedback["thumbs_up"] >= 1
            assert 0 <= feedback["thumbs_up_ratio"] <= 1
        finally:
            await transaction.rollback()
    await engine.dispose()
