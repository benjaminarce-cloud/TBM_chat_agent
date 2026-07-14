import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import Settings


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_widget_token(
    session_id: uuid.UUID, parent_origin: str, widget_origin: str, settings: Settings
) -> str:
    payload = {
        "sid": str(session_id),
        "parent_origin": parent_origin.rstrip("/"),
        "widget_origin": widget_origin.rstrip("/"),
        "exp": int(time.time()) + settings.widget_token_ttl_seconds,
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = hmac.new(
        settings.widget_token_secret.encode(), encoded.encode(), hashlib.sha256
    ).digest()
    return f"{encoded}.{_b64encode(signature)}"


def decode_widget_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(
            settings.widget_token_secret.encode(), encoded.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_b64decode(supplied_signature), expected_signature):
            raise ValueError("invalid signature")
        payload = json.loads(_b64decode(encoded))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired token")
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid widget token"
        ) from exc


def require_allowed_origin(origin: str | None, allowed: set[str], settings: Settings) -> str:
    if origin:
        normalized = origin.rstrip("/")
        if normalized in allowed:
            return normalized
    if not origin and settings.environment.lower() in {"development", "test"}:
        return "http://localhost:3000"
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin is not allowed")


def authorize_widget_request(
    request: Request,
    session_id: uuid.UUID,
    authorization: str | None,
    settings: Settings,
) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing widget token")
    payload = decode_widget_token(authorization.removeprefix("Bearer ").strip(), settings)
    widget_origin = require_allowed_origin(
        request.headers.get("origin"), settings.widget_origins, settings
    )
    parent_origin = request.headers.get("x-widget-origin", "").rstrip("/")
    if str(session_id) != payload.get("sid"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token session mismatch")
    if widget_origin != payload.get("widget_origin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Widget origin mismatch")
    if (
        parent_origin != payload.get("parent_origin")
        or parent_origin not in settings.parent_origins
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parent origin mismatch")
    return payload


def hash_ip(ip: str, settings: Settings) -> str:
    return hmac.new(settings.ip_hash_salt.encode(), ip.encode(), hashlib.sha256).hexdigest()
