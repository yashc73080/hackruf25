#!/usr/bin/env python3
"""Simple test runner for the GitHub scraper.

Usage:
  python test_scrape_user.py <github_username>

This will print JSON to stdout.
"""
import json
import sys
from github_scraper import summarize_user


def main():
    if len(sys.argv) < 2:
        print("usage: python test_scrape_user.py <github_username>")
        sys.exit(1)
    username = sys.argv[1]
    result = summarize_user(username)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
