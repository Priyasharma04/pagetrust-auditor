# Architecture

```text
Next.js dashboard
  │
  ├── POST /api/audits ───────┐
  │                            │
FastAPI API                    │
  │                            │
  ├── Background job runner ◄──┘
  │
  ├── Crawler
  │     ├── Playwright for JS-rendered pages
  │     └── httpx fallback
  │
  ├── Extractors
  │     ├── Clickable elements
  │     ├── Visible text
  │     ├── Local business details
  │     └── SEO/schema metadata
  │
  ├── Auditors
  │     ├── Link checker with async httpx
  │     ├── Semantic alignment rules + optional Sentence Transformers
  │     ├── Contradiction rules + optional LLM/NLI
  │     ├── Unsupported claim checker
  │     └── Local SEO checker
  │
  ├── Trust score engine
  ├── Prompt generator
  ├── PDF/JSON exporter
  └── Storage
        ├── local JSON default
        └── optional Supabase table
```

## Priority logic

High priority:
- broken CTA/contact/direction links
- missing contact method
- missing address/directions
- major contradictions
- unsupported license/ranking/trust claims

Medium priority:
- generic AI copy
- semantic business mismatch
- weak local/category grounding
- missing hours/services/schema

Low priority:
- grammar/punctuation-style polish
- thin title/meta
- image alt gaps
- H1 structure
