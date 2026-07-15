import uuid

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.security import create_widget_token, decode_widget_token


def test_widget_token_is_signed_and_session_scoped() -> None:
    settings = Settings(
        environment="test",
        widget_token_secret="a" * 32,
        ip_hash_salt="b" * 32,
    )
    session_id = uuid.uuid4()
    token = create_widget_token(
        session_id, "http://localhost:3000", "http://localhost:3000", settings
    )
    claims = decode_widget_token(token, settings)
    assert claims["sid"] == str(session_id)
    assert claims["parent_origin"] == "http://localhost:3000"
    with pytest.raises(HTTPException):
        decode_widget_token(token + "tampered", settings)


def test_neon_urls_are_normalized_for_sqlalchemy_asyncpg() -> None:
    settings = Settings(
        environment="test",
        database_url=(
            "postgresql://user:secret@example-pooler.neon.tech/neondb"
            "?sslmode=require&channel_binding=require"
        ),
        database_url_unpooled=(
            "postgresql://user:secret@example.neon.tech/neondb"
            "?sslmode=require&channel_binding=require"
        ),
    )
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in settings.database_url
    assert "sslmode" not in settings.database_url
    assert "channel_binding" not in settings.database_url
    assert settings.database_url_unpooled is not None
    assert settings.database_url_unpooled.startswith("postgresql+asyncpg://")
