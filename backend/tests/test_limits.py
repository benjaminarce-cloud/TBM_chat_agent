from app.services.rate_limit import apply_token_bucket
from app.services.safety import capped_handoff, should_cap_after_increment


def test_token_bucket_denies_when_empty_and_refills_over_time() -> None:
    denied = apply_token_bucket(0, elapsed_seconds=0, capacity=5, refill_per_second=1)
    assert denied.allowed is False
    assert denied.remaining == 0
    allowed = apply_token_bucket(0, elapsed_seconds=1, capacity=5, refill_per_second=1)
    assert allowed.allowed is True
    assert allowed.remaining == 0


def test_session_hard_caps_on_twentieth_user_message() -> None:
    assert should_cap_after_increment(18, 20) is False
    assert should_cap_after_increment(19, 20) is True
    assert "limit" in capped_handoff("en").lower()
    assert "límite" in capped_handoff("es").lower()
