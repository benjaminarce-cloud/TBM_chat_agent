from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RateLimitBucket


@dataclass(frozen=True)
class BucketResult:
    allowed: bool
    remaining: float


def refill_tokens(
    previous_tokens: float,
    elapsed_seconds: float,
    capacity: float,
    refill_per_second: float,
) -> float:
    return min(capacity, previous_tokens + max(0.0, elapsed_seconds) * refill_per_second)


def apply_token_bucket(
    previous_tokens: float,
    elapsed_seconds: float,
    capacity: float,
    refill_per_second: float,
    cost: float = 1.0,
) -> BucketResult:
    available = refill_tokens(previous_tokens, elapsed_seconds, capacity, refill_per_second)
    allowed = available >= cost
    return BucketResult(allowed=allowed, remaining=available - cost if allowed else available)


async def consume(
    db: AsyncSession,
    key: str,
    capacity: int,
    refill_per_minute: float,
    cost: float = 1.0,
) -> BucketResult:
    """Persistent token bucket. The row lock serializes requests for an existing bucket."""
    now = datetime.now(UTC)
    if db.get_bind().dialect.name == "postgresql":
        # Serialize first-use inserts too; SELECT FOR UPDATE cannot lock a missing row.
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )
    bucket = await db.get(RateLimitBucket, key, with_for_update=True)
    if bucket is None:
        remaining = float(capacity) - cost
        db.add(RateLimitBucket(key=key, tokens=max(0.0, remaining), updated_at=now))
        return BucketResult(allowed=remaining >= 0, remaining=max(0.0, remaining))

    updated_at = bucket.updated_at
    # SQLite drops timezone metadata even for timezone-aware columns. Treat those
    # values as UTC so the same persistent limiter works in local and CI runs.
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    elapsed = (now - updated_at).total_seconds()
    result = apply_token_bucket(
        bucket.tokens, elapsed, float(capacity), refill_per_minute / 60.0, cost
    )
    bucket.tokens = result.remaining
    bucket.updated_at = now
    return result
