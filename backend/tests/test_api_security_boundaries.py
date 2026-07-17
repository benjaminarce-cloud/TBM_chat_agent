from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.db import get_db
from app.main import app
from app.models import Base, Consent, Lead, Message


@pytest.mark.asyncio
async def test_message_is_rejected_until_current_affirmative_consent() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    settings = Settings(
        environment="test",
        widget_token_secret="a" * 32,
        ip_hash_salt="b" * 32,
        privacy_notice_version="approved-v1",
    )

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with sessions() as db:
            yield db

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/session",
                headers={"Origin": "http://localhost:3000"},
                json={"locale": "en", "parent_origin": "http://localhost:3000"},
            )
            assert created.status_code == 201
            payload = created.json()
            session_id = payload["session_id"]
            auth = {
                "Authorization": f"Bearer {payload['widget_token']}",
                "Origin": "http://localhost:3000",
                "X-Widget-Origin": "http://localhost:3000",
            }

            denied = await client.post(
                f"/api/session/{session_id}/message",
                headers=auth,
                json={"content": "private@example.com"},
            )
            assert denied.status_code == 403

            false_ack = await client.post(
                f"/api/session/{session_id}/consent",
                headers=auth,
                json={
                    "notice_version": "approved-v1",
                    "locale": "en",
                    "cross_border_ack": False,
                },
            )
            assert false_ack.status_code == 422

            wrong_version = await client.post(
                f"/api/session/{session_id}/consent",
                headers=auth,
                json={
                    "notice_version": "caller-selected-version",
                    "locale": "en",
                    "cross_border_ack": True,
                },
            )
            assert wrong_version.status_code == 400

            accepted = await client.post(
                f"/api/session/{session_id}/consent",
                headers=auth,
                json={
                    "notice_version": "approved-v1",
                    "locale": "en",
                    "cross_border_ack": True,
                },
            )
            assert accepted.status_code == 201

        async with sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Consent)) == 1
            assert await db.scalar(select(func.count()).select_from(Message)) == 0
            assert await db.scalar(select(func.count()).select_from(Lead)) == 0
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
