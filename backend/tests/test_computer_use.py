import pytest

from app.services.computer_use import (
    _actions_from_call,
    _execute_actions,
    _is_public_address,
    allowed_start_url,
)


def test_computer_use_allows_exact_https_host() -> None:
    assert allowed_start_url("https://example.com/path", {"example.com"})
    assert not allowed_start_url("https://sub.example.com/path", {"example.com"})
    assert not allowed_start_url("https://example.com.attacker.test", {"example.com"})
    assert not allowed_start_url("https://user@example.com", {"example.com"})
    assert not allowed_start_url("https://example.com:8443", {"example.com"})


def test_computer_use_rejects_non_http_urls() -> None:
    assert not allowed_start_url("file:///tmp/page.html", {"localhost"})
    assert not allowed_start_url("javascript:alert(1)", {"localhost"})
    assert not allowed_start_url("http://example.com", {"example.com"})


def test_private_network_addresses_are_rejected() -> None:
    assert _is_public_address("8.8.8.8")
    assert not _is_public_address("127.0.0.1")
    assert not _is_public_address("169.254.169.254")
    assert not _is_public_address("10.0.0.1")


async def test_state_changing_computer_action_is_rejected() -> None:
    action = type("Action", (), {"type": "click", "x": 1, "y": 1})()
    try:
        await _execute_actions(object(), [action])
    except PermissionError as exc:
        assert "not read-only" in str(exc)
    else:
        raise AssertionError("click action was not rejected")


def test_api_safety_checks_are_never_acknowledged_automatically() -> None:
    call = type("Call", (), {"pending_safety_checks": [object()], "actions": []})()
    with pytest.raises(PermissionError, match="safety check"):
        _actions_from_call(call)
