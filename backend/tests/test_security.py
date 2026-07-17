import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.api.routes import _client_ip
from app.config import Settings
from app.main import RequestBodyLimitMiddleware
from app.schemas import ConsentCreate
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


def test_consent_requires_affirmative_cross_border_acknowledgement() -> None:
    with pytest.raises(ValidationError):
        ConsentCreate(notice_version="approved-v1", locale="en", cross_border_ack=False)


def test_client_ip_ignores_untrusted_forwarding_header() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"203.0.113.44")],
            "client": ("10.0.0.7", 1234),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )
    assert _client_ip(request) == "10.0.0.7"


async def test_request_body_limit_counts_chunked_bytes() -> None:
    async def consume_body(scope, receive, send) -> None:
        while True:
            message = await receive()
            if not message.get("more_body"):
                break

    middleware = RequestBodyLimitMiddleware(consume_body, max_bytes=4)
    chunks = iter(
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.request", "body": b"def", "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(chunks)

    async def send(message) -> None:
        sent.append(message)

    await middleware({"type": "http", "path": "/api/session", "headers": []}, receive, send)
    assert sent[0]["status"] == 413


def test_production_rejects_insecure_transport_and_placeholder_notice() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url="postgresql://user:secret@example.com/db?sslmode=disable",
            anthropic_api_key="configured",
            widget_token_secret="a" * 32,
            ip_hash_salt="b" * 32,
            allowed_widget_origins="http://widget.example.com",
            allowed_parent_origins="https://example.com",
            privacy_notice_version="development-placeholder-v0",
        )
