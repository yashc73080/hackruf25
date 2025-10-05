#!/usr/bin/env python3
"""Simple CLI tester for the GitHub scraper.

Usage:
    python teamskills/backend/test_github_scraper.py <github_username>

This script calls `summarize_user(username)` and prints a compact JSON
summary. Returns exit code 0 on success, 2 on extraction errors.

Examples (copy & paste into your terminal):

    # Run the tester against Linus Torvalds' account
    python teamskills/backend/test_github_scraper.py torvalds

    # Run with the GitHub "octocat" demo user
    python teamskills/backend/test_github_scraper.py octocat

    # Some users to try:
    python teamskills/backend/test_github_scraper.py yashc73080
    python teamskills/backend/test_github_scraper.py ayushmish605

"""

import sys
from pathlib import Path
import json

# When this file is run directly (python teamskills/backend/test_github_scraper.py ...)
# the package root may not be on sys.path, which causes "No module named 'teamskills'".
# Ensure the repository root is inserted onto sys.path so imports like
# `from teamskills.backend.github_scraper import summarize_user` work the same
# whether the tester is executed as a module (`-m`) or as a script.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from teamskills.backend.github_scraper import summarize_user


def main(argv):
    username = argv[1] if len(argv) > 1 else "yashc73080"
    try:
        res = summarize_user(username)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
