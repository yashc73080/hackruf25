#!/usr/bin/env python3
import json
import sys
from github_scraper import summarize_user
from skills_engine import match_project

"""
Run locally:
python3 teamskills/backend/run_match.py "build a backend with FastAPI and Postgres"

It will scrape the default username (from args) and print a ranking.
"""

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python run_match.py '<requirement text>' [username1 username2 ...]")
        sys.exit(1)
    req = sys.argv[1]
    usernames = sys.argv[2:] or ["yashc73080"]
    profiles = {}
    for u in usernames:
        print(f"Scraping {u}...")
        profiles[u] = summarize_user(u)
    ranked = match_project(req, profiles)
    print(json.dumps([{"user": u, "score": s, "matched": m} for u, s, m in ranked], indent=2))
