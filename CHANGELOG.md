# Changelog

## 2025-10-04 — vibecoding
- Fix: `recent_pushes_30d` now uses timezone-aware parsing and falls back to counting repos with recent `updated_at`/`pushed_at` timestamps when public PushEvents are not available.
- Add: README fetch with on-disk caching to avoid repeated API calls during development.
- Add: `teamskills/backend/test_scrape_user.py` and `teamskills/backend/test_smoke_scraper.py` for smoke tests.
- CI: GitHub Actions workflow `.github/workflows/smoke-test.yml` added to run smoke tests on pushes to `vibecoding`.
- Repo hygiene: remove generated cache files and add `.cache/` to `.gitignore`.
