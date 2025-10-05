# Changelog

## 2025-10-04 — vibecoding
- Fix: `recent_pushes_30d` now uses timezone-aware parsing and falls back to counting repos with recent `updated_at`/`pushed_at` timestamps when public PushEvents are not available.
- Add: README fetch with on-disk caching to avoid repeated API calls during development.
- Add: `teamskills/backend/test_scrape_user.py` and `teamskills/backend/test_smoke_scraper.py` for smoke tests.
- CI: GitHub Actions workflow `.github/workflows/smoke-test.yml` added to run smoke tests on pushes to `vibecoding`.
- Repo hygiene: remove generated cache files and add `.cache/` to `.gitignore`.
 - Add: `teamskills/backend/gemini_helper.py` — Gemini (Generative AI) helper for extracting normalized skill tokens from resume/README text with on-disk caching and retries.
 - Change: `teamskills/backend/resume_scraper.py` now writes a human-readable Markdown extraction report (includes extracted text snippet, extracted skills from Gemini, and raw LLM response) and saves the original upload to `teamskills/uploads/` for traceability.
 - Add: `gemini_helper` supports `domain_priority` (default `cs`) so extractions can prioritize computer-science skills or domain-specific vocabularies (e.g., `medical`, `finance`).
 - Add: local fallback heuristic in `gemini_helper` so the pipeline still works if the generative client isn't installed; outputs are cached under `.cache/gemini`.
 - Remove: experimental deterministic `skills_engine.py` and `skills_fallback.json` (migrated to Gemini-only extraction per project direction).
