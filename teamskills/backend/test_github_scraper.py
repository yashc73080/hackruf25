#!/usr/bin/env python3
"""Simple CLI tester for the GitHub scraper.

Usage:
  python teamskills/backend/test_github_scraper.py <github_username>

This script calls `summarize_user(username)` and prints a compact JSON
summary. Returns exit code 0 on success, 2 on extraction errors.
"""

import sys
import json
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
