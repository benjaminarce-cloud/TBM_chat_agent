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
