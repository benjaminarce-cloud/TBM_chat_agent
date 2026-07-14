import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import SessionLocal, get_db
from app.models import Consent, Session
from app.schemas import (
    ConsentCreate,
    FeedbackCreate,
    MessageCreate,
    SessionCreate,
    SessionCreated,
    TurnAnalysis,
)
from app.security import (
    authorize_widget_request,
    create_widget_token,
    hash_ip,
    require_allowed_origin,
)
from app.services.email import send_handoff_if_needed
from app.services.llm import ClaudeService, LLMStreamItem, estimated_cost_usd
from app.services.rate_limit import consume
from app.services.repository import (
    get_history,
    lead_is_captured,
    lock_session,
    persist_message_if_consented,
    record_event,
    upsert_lead_fields,
)
from app.services.safety import (
    capped_handoff,
    contains_price_value,
    forced_response,
    pricing_pivot,
    safe_failure,
    should_cap_after_increment,
)

router = APIRouter(prefix="/api")


def _sse(event: str, data: dict | str) -> bytes:
    payload = data if isinstance(data, str) else json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()


def _client_ip(request: Request) -> str:
    # Trust proxy normalization to the hosting platform; never store this raw value.
    forwarded = request.headers.get("x-forwarded-for", "")
    return (forwarded.split(",", 1)[0].strip() if forwarded else "") or (
        request.client.host if request.client else "unknown"
    )


def _safe_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname
        if parsed.port:
            host = f"{host}:{parsed.port}"
        path = parsed.path[:300]
        # URL paths occasionally contain contact data; retain only the host in that case.
        if "@" in path or re.search(r"\d[\d(). +\-]{7,}\d", path):
            path = "/"
        return urlunsplit((parsed.scheme, host, path, "", ""))
    except ValueError:
        return None


def _sanitize_source(body: SessionCreate, request: Request) -> dict:
    source = body.source.model_dump(exclude_none=True) if body.source else {}
    source["page"] = _safe_url(source.get("page"))
    source["referrer"] = _safe_url(source.get("referrer"))
    source["user_agent"] = request.headers.get("user-agent", "")[:500]
    if "utm" in source:
        source["utm"] = {
            str(key)[:60]: str(value)[:120]
            for key, value in source["utm"].items()
            if key in {"source", "medium", "campaign"}
            and "@" not in str(value)
            and not re.search(r"\d[\d(). +\-]{7,}\d", str(value))
        }
    return {key: value for key, value in source.items() if value}


def _authorized(
    request: Request,
    session_id: uuid.UUID,
    authorization: str | None,
    settings: Settings,
) -> None:
    authorize_widget_request(request, session_id, authorization, settings)


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.post("/session", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SessionCreated:
    widget_origin = require_allowed_origin(
        request.headers.get("origin"), settings.widget_origins, settings
    )
    parent_origin = body.parent_origin.rstrip("/")
    if parent_origin not in settings.parent_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Parent origin is not allowed"
        )

    ip_key = hash_ip(_client_ip(request), settings)
    limit = await consume(
        db,
        f"session-create:ip:{ip_key}",
        settings.ip_rate_limit_capacity,
        settings.ip_rate_limit_refill_per_minute,
    )
    if not limit.allowed:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )

    kb_version = (
        settings.kb_version_path.read_text(encoding="utf-8").strip()
        if settings.kb_version_path.exists()
        else "uncompiled"
    )
    session = Session(
        locale=body.locale,
        kb_version=kb_version,
        source=_sanitize_source(body, request),
    )
    db.add(session)
    await db.flush()
    await record_event(db, session.id, "session_start", {"locale": body.locale})
    await db.commit()
    return SessionCreated(
        session_id=session.id,
        widget_token=create_widget_token(session.id, parent_origin, widget_origin, settings),
    )


@router.post("/session/{session_id}/consent", status_code=status.HTTP_201_CREATED)
async def grant_consent(
    session_id: uuid.UUID,
    body: ConsentCreate,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    _authorized(request, session_id, authorization, settings)
    if not await db.get(Session, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    consent = Consent(
        session_id=session_id,
        notice_version=body.notice_version,
        locale=body.locale,
        cross_border_ack=body.cross_border_ack,
        ip_hash=hash_ip(_client_ip(request), settings),
    )
    db.add(consent)
    await db.flush()
    await record_event(
        db,
        session_id,
        "consent_granted",
        {"notice_version": body.notice_version, "locale": body.locale},
    )
    await db.commit()
    return {"consent_id": str(consent.id)}


@router.post("/session/{session_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def feedback(
    session_id: uuid.UUID,
    body: FeedbackCreate,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    _authorized(request, session_id, authorization, settings)
    if not await db.get(Session, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    await record_event(db, session_id, "feedback", {"thumbs": body.thumbs})
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _finalize_turn(
    session_id: uuid.UUID,
    assistant_text: str,
    analysis: TurnAnalysis,
    usage_items: list[LLMStreamItem],
    first_token_ms: int,
    full_latency_ms: int,
    settings: Settings,
) -> None:
    async with SessionLocal() as db:
        result = await upsert_lead_fields(db, session_id, analysis.extracted)
        await persist_message_if_consented(
            db, session_id, "assistant", assistant_text, full_latency_ms
        )
        await record_event(db, session_id, "first_token", {"latency_ms": first_token_ms})
        if analysis.escalate or analysis.intent in {"pricing_ask", "human_request"}:
            known_reasons = {
                "classification_unavailable",
                "unsafe_model_output_blocked",
            }
            reason = (
                analysis.escalate_reason
                if analysis.escalate_reason in known_reasons
                else analysis.intent
            )
            await record_event(
                db,
                session_id,
                "escalated",
                {"reason": reason},
            )
        for item in usage_items:
            payload = {
                "model": item.model,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
            }
            estimated = estimated_cost_usd(item, settings)
            if estimated is not None:
                payload["estimated_cost_usd"] = estimated
            await record_event(db, session_id, "llm_usage", payload)
        if result.lead and lead_is_captured(result.lead):
            await send_handoff_if_needed(db, session_id, result.lead, settings)
        await db.commit()


async def _capped_stream(
    session_id: uuid.UUID, locale: str, started: float
) -> AsyncIterator[bytes]:
    text_value = capped_handoff(locale)
    yield _sse("token", {"text": text_value})
    elapsed = int((time.perf_counter() - started) * 1000)
    async with SessionLocal() as db:
        await persist_message_if_consented(db, session_id, "assistant", text_value, elapsed)
        await record_event(db, session_id, "first_token", {"latency_ms": elapsed})
        await db.commit()
    yield _sse("done", {"capped": True})


@router.post("/session/{session_id}/message")
async def message(
    session_id: uuid.UUID,
    body: MessageCreate,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    started = time.perf_counter()
    _authorized(request, session_id, authorization, settings)

    ip_limit = await consume(
        db,
        f"message:ip:{hash_ip(_client_ip(request), settings)}",
        settings.ip_rate_limit_capacity,
        settings.ip_rate_limit_refill_per_minute,
    )
    session_limit = await consume(
        db,
        f"message:session:{session_id}",
        settings.session_rate_limit_capacity,
        settings.session_rate_limit_refill_per_minute,
    )
    if not ip_limit.allowed or not session_limit.allowed:
        await record_event(db, session_id, "rate_limited", None)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )

    chat_session = await lock_session(db, session_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if (
        chat_session.status != "active"
        or chat_session.message_count >= settings.session_message_cap
    ):
        chat_session.status = "capped"
        await record_event(db, session_id, "capped", None)
        await db.commit()
        return StreamingResponse(
            _capped_stream(session_id, chat_session.locale, started),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    should_cap = should_cap_after_increment(
        chat_session.message_count, settings.session_message_cap
    )
    chat_session.message_count += 1
    if should_cap:
        chat_session.status = "capped"
        await record_event(db, session_id, "capped", None)
    history = await get_history(db, session_id)
    await persist_message_if_consented(db, session_id, "user", body.content)
    locale = chat_session.locale
    await db.commit()

    if should_cap:
        return StreamingResponse(
            _capped_stream(session_id, locale, started),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    claude = ClaudeService(settings)

    async def event_stream() -> AsyncIterator[bytes]:
        # Each call has a 400-token hard ceiling, so this queue is bounded by model output.
        queue: asyncio.Queue[LLMStreamItem | Exception | None] = asyncio.Queue()
        usage_items: list[LLMStreamItem] = []

        async def pump_sonnet() -> None:
            try:
                async for item in claude.stream_turn(body.content, locale, history):
                    await queue.put(item)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await queue.put(exc)
            finally:
                await queue.put(None)

        analysis_task = asyncio.create_task(claude.analyze_turn(body.content))
        sonnet_task = asyncio.create_task(pump_sonnet())
        analysis: TurnAnalysis
        try:
            analysis, haiku_usage = await analysis_task
            usage_items.append(haiku_usage)
        except Exception:
            # Fail closed: no unclassified Sonnet text can reach the visitor.
            analysis = TurnAnalysis(
                intent="human_request",
                escalate=True,
                escalate_reason="classification_unavailable",
                extracted={},
            )

        turn_locale = analysis.extracted.get("language", locale)
        forced = forced_response(analysis, turn_locale)
        complete_text = ""
        first_token_ms: int | None = None
        unsafe_output = False

        if forced is not None:
            sonnet_task.cancel()
            with suppress(asyncio.CancelledError):
                await sonnet_task
            complete_text = forced
            first_token_ms = int((time.perf_counter() - started) * 1000)
            yield _sse("token", {"text": forced})
        else:
            pending = ""
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    if not complete_text:
                        complete_text = safe_failure(turn_locale)
                        first_token_ms = int((time.perf_counter() - started) * 1000)
                        yield _sse("token", {"text": complete_text})
                    break
                if item.kind == "usage":
                    usage_items.append(item)
                    continue
                pending += item.text
                # Hold a sentence-sized safety buffer so split currency tokens cannot leak.
                if not any(mark in pending for mark in (". ", "? ", "! ", "\n")):
                    continue
                if contains_price_value(pending):
                    unsafe_output = True
                    pivot = pricing_pivot(turn_locale)
                    complete_text += pivot
                    if first_token_ms is None:
                        first_token_ms = int((time.perf_counter() - started) * 1000)
                    yield _sse("token", {"text": pivot})
                    sonnet_task.cancel()
                    break
                complete_text += pending
                if first_token_ms is None:
                    first_token_ms = int((time.perf_counter() - started) * 1000)
                yield _sse("token", {"text": pending})
                pending = ""
            if pending and not unsafe_output:
                if contains_price_value(pending):
                    pending = pricing_pivot(turn_locale)
                    unsafe_output = True
                complete_text += pending
                if first_token_ms is None:
                    first_token_ms = int((time.perf_counter() - started) * 1000)
                yield _sse("token", {"text": pending})
            with suppress(asyncio.CancelledError):
                await sonnet_task

        if unsafe_output:
            analysis = TurnAnalysis(
                intent="pricing_ask",
                escalate=True,
                escalate_reason="unsafe_model_output_blocked",
                extracted=analysis.extracted,
            )
        full_latency_ms = int((time.perf_counter() - started) * 1000)
        await _finalize_turn(
            session_id,
            complete_text,
            analysis,
            usage_items,
            first_token_ms or full_latency_ms,
            full_latency_ms,
            settings,
        )
        yield _sse("done", {"message_count": chat_session.message_count})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
