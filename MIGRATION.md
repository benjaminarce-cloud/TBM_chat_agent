# Pilot migration and ownership plan

This pilot starts under Benjamin's personal Vercel, Railway, Neon, Anthropic, and Resend accounts.
TBM remains the data controller. Personal-account hosting is temporary and must not become the
unreviewed long-term operating model.

## Named cutover target

**Proposed ownership cutover deadline: 2026-09-30.** TBM must approve or replace this date before
launch. By that date, production infrastructure, secrets, billing, access groups, incident contacts,
retention ownership, and vendor data-processing terms should be controlled by TBM. If approval is
not complete, pause new production lead collection rather than silently extending personal hosting.

## Cut over to TBM-owned infrastructure

1. Create new TBM-owned Vercel, Railway (or approved long-running container host), Neon, Anthropic,
   and Resend resources. Keep staging and production separate.
2. Enable `pgcrypto`, run `alembic upgrade head`, load reviewed KB documents, then run
   `python -m app.jobs.compile_kb` in both environments.
3. Move secrets through each provider's secret manager. Rotate token signing and IP-hash salts; do
   not copy personal-account secrets. Configure approved origins, rate limits, alert thresholds,
   sender identity, sales inbox, and admin inbox.
4. Export only retained, consented pilot data authorized by TBM's retention policy. Import it over
   TLS, verify row counts and consent links, then securely delete personal copies after written
   acceptance and any required backup-expiry window.
5. Deploy the API and verify health, migrations, consent gate, price probes, rate limits, email,
   purge, alerts, and analytics. Deploy the widget and verify both languages on mobile.
6. Create `agent.tbmcarriers.com` (and optionally `agent-staging.tbmcarriers.com`) as DNS records
   pointing to the new widget deployment. Use an API subdomain such as
   `agent-api.tbmcarriers.com` for Railway. Update origin allowlists before DNS cutover.
7. Change the host website's one script URL or keep the stable `agent.tbmcarriers.com/embed.js`
   URL. This is a DNS/embed change only; it does not require access to or code integration with
   TBM's main repository.
8. Lower DNS TTL in advance, shift traffic, watch health/events/handoff delivery, then revoke
   personal-account access and credentials after the acceptance window.

Rollback is the reverse DNS change to the last healthy deployment. Database rollback should use a
verified restore or forward fix; do not run destructive Alembic downgrades against captured leads
without written approval.

## Retrieval upgrade trigger

The launch KB is intentionally compiled into one prompt-cached Markdown block. Build Voyage
embeddings plus pgvector retrieval only when either condition is met:

- approved compiled content reaches roughly **30,000–50,000 tokens**, or
- grounding evals show material accuracy/recall degradation before that size.

At the trigger:

1. Add chunk and embedding tables plus a versioned indexing job; keep `kb_documents` as the source
   of truth.
2. Add a migration that enables pgvector, embed only approved documents, record model/version, and
   use vector retrieval for candidates. Add hybrid lexical/vector retrieval and reranking only if
   evals justify them.
3. Retrieve a small cited context set per turn while keeping the policy block prompt-cached.
4. Run bilingual grounding, stale-document, no-result, prompt-injection, and pricing evals before
   enabling retrieval in staging.
5. Roll out behind configuration and retain the compiled path for rollback until metrics stabilize.

This is additive. No initial extension migration or framework rewrite is required.

## Main-site integration boundary

The pilot never adds rate logic, CRM integration, embeddings, or code to TBM's main site. The only
eventual integration is a script include hosted on the agent subdomain. Any broader integration
requires a separate scope, security/privacy review, and ownership decision.
