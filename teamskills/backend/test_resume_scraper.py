#!/usr/bin/env python3
"""Simple CLI tester for resume_scraper.py
Usage:
    python -m teamskills.backend.test_resume_scraper <filename-or-path>

This tester accepts either a basename located in the repo-root `.uploads/`
directory, or a full/relative path to a resume file. Generated reports are
written into the repo-root cache: `.cache/resumes/<stem>.report.md`.
"""
import sys
import os
from pathlib import Path

try:
    from teamskills.backend.resume_scraper import main as resume_main
except Exception:
    # fallback: import as script
    resume_main = None


def run(path: str):
    repo_root = Path(__file__).resolve().parents[2]

    candidate = Path(path)
    # If a simple basename was provided and exists under .uploads, prefer that
    if not candidate.is_absolute() and (repo_root / ".uploads" / candidate).exists():
        in_path = repo_root / ".uploads" / candidate
    else:
        in_path = (candidate if candidate.is_absolute() else repo_root / candidate)

    if not in_path.exists():
        print(f"ERROR: input not found: {in_path}")
        return 2

    # default output into repo-root .cache/resumes
    out_dir = repo_root / ".cache" / "resumes"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{in_path.stem}.report.md"

    # call resume_scraper.py as script
    cmd = (
        f'"{sys.executable}" "{repo_root}/teamskills/backend/resume_scraper.py" '
        f'--input "{in_path}" --output "{out_path}"'
    )
    print("Running:", cmd)
    rc = os.system(cmd)
    if rc != 0:
        print("resume_scraper failed with exit code", rc)
        return rc

    print("Wrote report:", out_path)
    try:
        print(out_path.read_text()[:4000])
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m teamskills.backend.test_resume_scraper <filename-or-path>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
