# Knowledge base source

TBM must supply and approve the company information, services, lanes/coverage, FAQs,
and objection-handling content. Do not put unapproved company claims in an `approved`
row.

The application reads only a generated `compiled.md` file. Build it from the database:

```bash
python -m app.jobs.compile_kb
```

The compiler selects only `kb_documents.status = 'approved'`, orders by slug, writes a
single Markdown block, and stamps its SHA-256-derived version in `VERSION`. Both generated
files are intentionally ignored by Git so each environment compiles its own approved KB.
