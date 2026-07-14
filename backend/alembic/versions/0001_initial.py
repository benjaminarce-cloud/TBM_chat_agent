"""Initial pgvector-ready pilot schema and analytics views.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


TABLES_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  locale TEXT NOT NULL DEFAULT 'es',
  kb_version TEXT,
  source JSONB,
  message_count INT NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  CONSTRAINT sessions_locale_check CHECK (locale IN ('es', 'en')),
  CONSTRAINT sessions_status_check CHECK (status IN ('active', 'ended', 'capped', 'abusive'))
);

CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  latency_ms INT,
  CONSTRAINT messages_role_check CHECK (role IN ('user', 'assistant'))
);

CREATE TABLE consents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  notice_version TEXT NOT NULL,
  locale TEXT NOT NULL,
  cross_border_ack BOOLEAN NOT NULL DEFAULT false,
  ip_hash TEXT
);

CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  consent_id UUID REFERENCES consents(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'new',
  name TEXT,
  company TEXT,
  email TEXT,
  phone TEXT,
  preferred_contact TEXT,
  language TEXT,
  lane_origin_city TEXT,
  lane_origin_state TEXT,
  lane_origin_country TEXT,
  lane_dest_city TEXT,
  lane_dest_state TEXT,
  lane_dest_country TEXT,
  freight_type TEXT,
  equipment TEXT,
  volume_amount INT,
  volume_period TEXT,
  target_ship_date DATE,
  cross_border BOOLEAN,
  notes TEXT,
  qualification_score INT,
  CONSTRAINT leads_status_check CHECK (status IN ('new', 'contacted', 'qualified', 'disqualified', 'won')),
  CONSTRAINT leads_equipment_check CHECK (equipment IS NULL OR equipment IN ('dry_van', 'reefer', 'flatbed', 'other', 'unknown')),
  CONSTRAINT leads_volume_period_check CHECK (volume_period IS NULL OR volume_period IN ('one_time', 'weekly', 'monthly', 'unknown')),
  CONSTRAINT leads_preferred_contact_check CHECK (preferred_contact IS NULL OR preferred_contact IN ('email', 'phone', 'whatsapp')),
  CONSTRAINT leads_country_codes_check CHECK (
    (lane_origin_country IS NULL OR char_length(lane_origin_country) = 2) AND
    (lane_dest_country IS NULL OR char_length(lane_dest_country) = 2)
  )
);

CREATE TABLE kb_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  title_en TEXT,
  title_es TEXT,
  body_md TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT kb_documents_status_check CHECK (status IN ('draft', 'approved', 'retired'))
);

CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  type TEXT NOT NULL,
  payload JSONB
);

CREATE TABLE rate_limit_buckets (
  key TEXT PRIMARY KEY,
  tokens DOUBLE PRECISION NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_messages_session_id ON messages (session_id);
CREATE INDEX ix_consents_session_id ON consents (session_id);
CREATE INDEX ix_leads_session_id ON leads (session_id);
CREATE INDEX ix_events_session_id_type ON events (session_id, type);
"""


VIEWS_SQL = """
CREATE VIEW analytics_engagement AS
SELECT
  COUNT(*) AS sessions_started,
  COUNT(*) FILTER (WHERE EXISTS (
    SELECT 1 FROM events e WHERE e.session_id = s.id AND e.type = 'message'
      AND e.payload->>'role' = 'user'
  )) AS engaged_sessions,
  COALESCE(
    COUNT(*) FILTER (WHERE EXISTS (
      SELECT 1 FROM events e WHERE e.session_id = s.id AND e.type = 'message'
        AND e.payload->>'role' = 'user'
    ))::numeric / NULLIF(COUNT(*), 0), 0
  ) AS engagement_rate
FROM sessions s;

CREATE VIEW analytics_lead_capture AS
SELECT
  (SELECT COUNT(*) FROM sessions) AS sessions_started,
  COUNT(DISTINCT session_id) AS captured_leads,
  COALESCE(COUNT(DISTINCT session_id)::numeric / NULLIF((SELECT COUNT(*) FROM sessions), 0), 0)
    AS lead_capture_rate
FROM leads
WHERE (email IS NOT NULL OR phone IS NOT NULL)
  AND lane_origin_city IS NOT NULL AND lane_dest_city IS NOT NULL;

CREATE VIEW analytics_qualified_leads AS
WITH captured AS (
  SELECT DISTINCT ON (session_id) session_id, status
  FROM leads
  WHERE (email IS NOT NULL OR phone IS NOT NULL)
    AND lane_origin_city IS NOT NULL AND lane_dest_city IS NOT NULL
  ORDER BY session_id, updated_at DESC
)
SELECT
  COUNT(*) AS captured_leads,
  COUNT(*) FILTER (WHERE status = 'qualified') AS qualified_leads,
  COALESCE(COUNT(*) FILTER (WHERE status = 'qualified')::numeric / NULLIF(COUNT(*), 0), 0)
    AS qualified_lead_rate
FROM captured;

CREATE VIEW analytics_escalation AS
SELECT
  (SELECT COUNT(*) FROM sessions) AS sessions_started,
  COUNT(DISTINCT session_id) AS escalated_sessions,
  COALESCE(COUNT(DISTINCT session_id)::numeric / NULLIF((SELECT COUNT(*) FROM sessions), 0), 0)
    AS escalation_rate
FROM events
WHERE type = 'escalated';

CREATE VIEW analytics_latency AS
SELECT
  percentile_cont(0.5) WITHIN GROUP (ORDER BY (payload->>'latency_ms')::numeric)
    FILTER (WHERE type = 'first_token') AS median_first_token_ms,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY (payload->>'latency_ms')::numeric)
    FILTER (WHERE type = 'message' AND payload->>'role' = 'assistant') AS median_full_response_ms
FROM events
WHERE payload ? 'latency_ms';

CREATE VIEW analytics_feedback AS
SELECT
  COUNT(*) AS feedback_count,
  COUNT(*) FILTER (WHERE payload->>'thumbs' = 'up') AS thumbs_up,
  COALESCE(COUNT(*) FILTER (WHERE payload->>'thumbs' = 'up')::numeric / NULLIF(COUNT(*), 0), 0)
    AS thumbs_up_ratio
FROM events
WHERE type = 'feedback';
"""


def upgrade() -> None:
    # asyncpg prepares one statement at a time, so execute the static DDL individually.
    for statement in (TABLES_SQL + VIEWS_SQL).split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS analytics_feedback")
    op.execute("DROP VIEW IF EXISTS analytics_latency")
    op.execute("DROP VIEW IF EXISTS analytics_escalation")
    op.execute("DROP VIEW IF EXISTS analytics_qualified_leads")
    op.execute("DROP VIEW IF EXISTS analytics_lead_capture")
    op.execute("DROP VIEW IF EXISTS analytics_engagement")
    op.execute("DROP TABLE IF EXISTS rate_limit_buckets")
    op.execute("DROP TABLE IF EXISTS events")
    op.execute("DROP TABLE IF EXISTS kb_documents")
    op.execute("DROP TABLE IF EXISTS leads")
    op.execute("DROP TABLE IF EXISTS consents")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS sessions")
