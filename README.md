# TBM Carriers inbound sales/chat agent pilot

Standalone bilingual (English/Spanish) freight-lead qualification pilot. The visitor widget
collects shipment details, logs consent, progressively builds a lead, and emails a human sales
specialist. It never quotes, estimates, or ranges prices.

This repository is intentionally separate from TBM's main website and is designed for Benjamin's
personal Vercel, Railway, and Neon accounts during the pilot.

## What is included

- Next.js 16 iframe widget and one-tag embed loader in `frontend/`
- Async FastAPI and SSE API in `backend/`
- Direct Anthropic SDK calls: Haiku for classification/extraction and Sonnet for conversation
- Independent price controls in the Sonnet system prompt, Haiku classifier, and an output safety
  buffer that blocks monetary values before streaming
- Postgres/Alembic schema with a documented future pgvector retrieval migration
- Consent-gated transcript and lead persistence (no transcript text is stored before consent)
- Persistent IP/session token buckets and a hard 20-user-message cap
- Progressive lead upsert, deterministic qualification score, and Resend handoff email
- KB compiler, bounded-retention purge job, daily threshold alert job, SQL analytics views, eval fixtures,
  load test, and CI

## Human decisions required before production

These are deliberately not filled in by the implementation:

1. **Privacy copy:** the checked-in values are an internal pilot draft only. TBM/counsel must
   replace `PRIVACY_NOTICE_ES`, `PRIVACY_NOTICE_EN`, and `PRIVACY_NOTICE_VERSION` with approved
   copy before any public use. Production startup/build fails if the version or copy is missing.
2. **Knowledge base:** TBM must provide and approve service, coverage, lane, FAQ, and objection
   content. The compiler currently emits a no-approved-facts marker rather than inventing claims.
3. **Handoff routing:** the pilot includes a **Resend** adapter, but TBM must approve the sender and
   `HANDOFF_TO_EMAIL` inbox.
4. **Controls:** the checked-in rate-limit values are clearly labeled pilot defaults. TBM must
   approve the final thresholds and configure both daily alert thresholds.
5. **Infrastructure:** create separate staging and production projects under Benjamin's personal
   accounts; do not attach this repo to TBM's main Vercel organization or website repository.

## Local setup

Prerequisites: Node.js 20.9+, Python 3.12+, Docker, and an Anthropic API key.

```bash
docker compose up -d postgres

cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements-dev.lock
python -m playwright install chromium  # only needed when COMPUTER_USE_ENABLED=true
cp .env.example .env
alembic upgrade head
python -m app.jobs.compile_kb
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`, then use the lower-right launcher. The demo page contains no TBM
company claims; it exists only to exercise the embed.

## Embed

After the frontend and backend are deployed, a host page needs one tag:

```html
<script
  src="https://YOUR-WIDGET-HOST/embed.js"
  data-locale="es"
  data-accent="#ff5a36"
></script>
```

Add the widget host to `ALLOWED_WIDGET_ORIGINS` and the page host to
`ALLOWED_PARENT_ORIGINS`; list the same page origins in frontend `WIDGET_FRAME_ANCESTORS`. Session
tokens bind the session ID, widget origin, parent origin, and
expiration. Every session API call checks the signed token and both origins. The public endpoint
also applies persistent IP/session rate limits; origin checks are not treated as authentication.

## API

- `POST /api/session` creates a scoped session token.
- `POST /api/session/{id}/consent` logs the versioned consent and hashed IP.
- `POST /api/session/{id}/message` returns `text/event-stream` events named `token` and `done`.
- `POST /api/session/{id}/feedback` records the thumbs signal.
- `POST /api/computer-use` runs an internal, token-protected, allowlisted browser task when
  `COMPUTER_USE_ENABLED=true`; it is not connected to visitor chat sessions.
- `GET /api/health` checks database connectivity.

Computer-use requests require `X-Computer-Use-Token` and an exact public HTTPS hostname in
`COMPUTER_USE_ALLOWED_DOMAINS`. This endpoint is strictly read-only: the executor permits only
scroll, pointer movement, wait, and screenshots. Clicks, typing, keypresses, dragging, downloads,
private-network targets, and off-allowlist navigation are rejected. The browser starts with no
cookies or inherited environment variables and is bounded by request rate, concurrency, elapsed
time, and `COMPUTER_USE_MAX_STEPS`.

The message endpoint starts Haiku analysis and the Sonnet stream concurrently. No model text is
released until Haiku has classified the turn. Pricing, escalation, or off-topic results cancel
Sonnet and force fixed bilingual copy. Relevant Sonnet text is released through a sentence-sized
safety buffer, which blocks numeric monetary/rate patterns even if the conversational model
violates its prompt.

## Data and consent behavior

- Before consent, sessions and content-free analytics events may be stored, but the UI is disabled
  and the API rejects messages, so **no visitor text reaches storage or an LLM**.
- After consent, the current and future transcript can be stored. Pre-consent text is not backfilled.
- `upsert_lead_fields()` checks for consent inside the repository write boundary, independently of
  the route.
- A lead becomes captured only when it has email or phone, plus origin and destination cities.
- The first transition to captured sends one Resend handoff and fires `lead_captured` and
  `handoff_sent` events. Missing email configuration records `handoff_pending_config` instead.

The checked-in pilot notice is not legal advice and cannot be used for public launch. Managed
Postgres provides at-rest encryption; backend production startup rejects non-TLS database URLs and
non-HTTPS widget/parent origins.

## Knowledge base

Insert content into `kb_documents` as `draft`, complete human review, then change it to `approved`.
Compile only approved rows:

```bash
cd backend
python -m app.jobs.compile_kb
```

The generated Markdown and version hash are environment artifacts. Recompile before starting a new
release and restart the backend so new sessions stamp the current version. Retrieval is explicitly
out of scope; see [MIGRATION.md](./MIGRATION.md) for its trigger.

## Scheduled jobs

Configure Railway cron services (or equivalent) with the same image and environment:

```bash
# Daily, for example 08:00 UTC
python -m app.jobs.daily_alert

# Daily
python -m app.jobs.purge
```

The daily alert remains disabled until an admin email and the relevant threshold are set. Spend is
estimated from `llm_usage` events only after the per-million input/output rates are configured;
those values are operational telemetry and are never exposed to visitors.

The purge job deletes all transcript text and page context after `TRANSCRIPT_RETENTION_DAYS`
(90 by default). It deletes leads, consents/IP hashes, and source data after
`UNCAPTURED_RETENTION_DAYS` (90) for uncaptured/disqualified sessions and after
`CAPTURED_LEAD_RETENTION_DAYS` (365) for captured leads. Migration `0002` preserves legacy pilot
data for this internal test, but the new consent gate does not treat its old notice versions as
current consent.

For Neon, `DATABASE_URL` should be the pooled application connection and
`DATABASE_URL_UNPOOLED` the direct migration connection. Provider-standard URLs are normalized for
SQLAlchemy/asyncpg at runtime, and Alembic automatically prefers the unpooled URL.

## Analytics views

After `alembic upgrade head`, query:

```sql
SELECT * FROM analytics_engagement;
SELECT * FROM analytics_lead_capture;
SELECT * FROM analytics_qualified_leads;
SELECT * FROM analytics_escalation;
SELECT * FROM analytics_latency;
SELECT * FROM analytics_feedback;
```

These cover engagement, captured and qualified leads, escalation, median first-token/full-response
latency, and thumbs-up ratio. Content-free message events make engagement and latency measurable
even when a visitor never consents.

## Tests

```bash
cd backend
ruff format --check app tests
ruff check app tests
pytest -q -m 'not live_llm'

# Requires a migrated Postgres database
TEST_DATABASE_URL=postgresql+asyncpg://... pytest -q tests/test_analytics_views.py

# Calls Anthropic: 30+ extraction cases and 20 pricing probes
ANTHROPIC_API_KEY=... pytest -q -m live_llm

# Load/rate/cap exercise against a running API
locust -f tests/load/locustfile.py --host http://localhost:8000

cd ../frontend
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e

# Runs a bounded smoke test against a deployed widget and creates no lead/contact record
E2E_LIVE_URL=https://frontend-nine-delta-71.vercel.app npm run test:e2e:live
```

The deterministic suite includes strict extraction-schema fixtures, pricing pivots and output
blocking, consent denial, signed token scope, token-bucket behavior, the message cap, and mocked-API
browser flows for bilingual sales intake, quote rendering, pricing safety, and mobile overflow. Live
LLM evals are kept opt-in so CI is deterministic and cannot create unbounded model spend. The live
widget smoke workflow runs after successful Vercel deployments and can also be started manually;
it accepts the pilot notice and sends only the sales shortcut, without contact details.

## Deployment map

| Surface | Pilot provider | Staging/prod rule |
| --- | --- | --- |
| Widget | Vercel personal account | Separate Vercel projects and environment values |
| API + cron | Railway personal account | Separate services/projects; health path `/api/health` |
| Postgres | Neon personal account | Separate databases/roles; enable `pgcrypto`; defer `vector` until the retrieval trigger |
| Email | Resend | Separate test/production sender configuration |

Run migrations and compile the approved KB before shifting traffic. No CRM, rate engine, embeddings,
or main-site repository integration belongs in this pilot.

Set `FORWARDED_ALLOW_IPS` to only the hosting platform's trusted proxy IPs/CIDRs. The application
uses Uvicorn's normalized client address and never parses `X-Forwarded-For` itself. Production
containers run as a non-root user; Python and container dependencies plus CI actions are pinned.
