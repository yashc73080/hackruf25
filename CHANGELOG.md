# Changelog

## 2025-10-04 — vibecoding
- Fix: `recent_pushes_30d` now uses timezone-aware parsing and falls back to counting repos with recent `updated_at`/`pushed_at` timestamps when public PushEvents are not available.
- Add: README fetch with on-disk caching to avoid repeated API calls during development.
- Add: `teamskills/backend/test_scrape_user.py` and `teamskills/backend/test_smoke_scraper.py` for smoke tests.
- CI: GitHub Actions workflow `.github/workflows/smoke-test.yml` added to run smoke tests on pushes to `vibecoding`.
- Repo hygiene: remove generated cache files and add `.cache/` to `.gitignore`.

### Added (vibecoding) — Gemini & resume improvements
- Add: `teamskills/backend/gemini_helper.py` — helper that calls Gemini (google-generativeai) to extract normalized skill tokens from resume or README text; includes disk caching, retries, and domain hinting (e.g. `cs`, `medical`).
- Change: `teamskills/backend/resume_scraper.py` updated to emit a Markdown report (includes extractor used, excerpt of extracted text, Gemini-extracted normalized tokens, and raw LLM response) and to save uploaded resumes to `teamskills/uploads/` for traceability.
- Change: `teamskills/backend/github_scraper.py` and other scrapers were updated during the branch to fetch README snippets, per-repo language percentages, and to add caching and robust recent-activity counting.
- Remove: experimental deterministic `skills_engine.py` and `skills_fallback.json` (now replaced by Gemini-driven extraction).

Notes:
- Gemini integration requires `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) set in the environment. To use Google Vision OCR fallback, set `GOOGLE_APPLICATION_CREDENTIALS` to your service account JSON.
- The gemini helper uses a conservative prompt and minimal normalization by default; we should iterate on prompt templates and synonym maps for higher precision.
