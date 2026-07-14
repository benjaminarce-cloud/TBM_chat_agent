## Pilot readiness checklist

- [ ] **BLOCKER:** TBM/counsel replaced and approved both legal notice placeholders; the notice
      version is no longer `pilot-placeholder-v0-legal-review-required`.
- [ ] **BLOCKER:** TBM supplied and approved actual KB facts; no draft/unapproved claim is compiled.
- [ ] TBM approved the Resend sender and handoff/admin inboxes.
- [ ] TBM approved IP/session limits and daily session/spend thresholds.
- [ ] Staging and production use separate personal pilot resources, not TBM's main website repo or
      Vercel org.
- [ ] Migrations and KB compilation ran in the target environment.
- [ ] EN/ES end-to-end, consent gate, pricing probes, rate/cap load test, handoff email, purge job,
      alert job, and all analytics views were verified.
- [ ] Proposed 2026-09-30 org-ownership cutover date was approved or replaced.

## Explicit scope boundary

No real-time pricing, CRM integration, embeddings/retrieval, behavioral scoring, or model-authored
urgency/scarcity language is included.
