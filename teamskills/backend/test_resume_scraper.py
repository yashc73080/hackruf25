#!/usr/bin/env python3
"""Small CLI tester for `teamskills.backend.resume_scraper`.

Usage:
    python -m teamskills.backend.test_resume_scraper <resume_basename_or_path>

Behavior:
 - If a basename is provided and it exists under repo-root `.uploads/`, that file is used.
 - Otherwise the provided path is used as-is (absolute or relative to repo root).
 - The tester invokes the scraper via the same Python interpreter (keeps venv).
 - Output report is created at repo-root `.cache/resumes/<stem>.report.txt` and a short preview is printed.

Examples (copy & paste into your terminal):

    # If you placed resumes in the repo .uploads directory, pass the basename:
    python -m teamskills.backend.test_resume_scraper Resume___Ayush_Mishra___Fall_2025.png
    python -m teamskills.backend.test_resume_scraper Resume___Ayush_Mishra___Fall_2025.pdf

"""
import sys
import subprocess
from pathlib import Path
import argparse

# Ensure repo root is on sys.path when run as a script so imports resolve
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_DIR = REPO_ROOT / ".uploads"
CACHE_RESUMES = REPO_ROOT / ".cache" / "resumes"
SCRAPER_MODULE = "teamskills.backend.resume_scraper"


def resolve_input(path_or_basename: str) -> Path:
    p = Path(path_or_basename)
    if p.is_absolute() and p.exists():
        return p
    # check relative to repo root
    rel = REPO_ROOT / p
    if rel.exists():
        return rel
    # check uploads
    up = UPLOADS_DIR / p
    if up.exists():
        return up
    raise FileNotFoundError(f"Input file not found: {path_or_basename} (tried exact, repo-root relative, and .uploads)")


def make_output_path(input_path: Path) -> Path:
    CACHE_RESUMES.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    return CACHE_RESUMES / f"{stem}.report.txt"


def run_scraper(input_path: Path, output_path: Path) -> None:
    cmd = [sys.executable, "-m", SCRAPER_MODULE, "--input", str(input_path), "--output", str(output_path)]
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("Resume scraper failed:\n", proc.stdout, proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    if proc.stdout:
        print(proc.stdout)


def preview_file(path: Path, nchars: int = 600) -> None:
    if not path.exists():
        print(f"Expected output not found: {path}", file=sys.stderr)
        return
    txt = path.read_text(encoding="utf-8", errors="replace")
    preview = txt[:nchars]
    print(f"\nReport: {path}\n--- Preview ({len(preview)} chars) ---\n")
    print(preview)
    if len(txt) > nchars:
        print("\n... (truncated) ...\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Resume basename (in .uploads) or full path")
    args = ap.parse_args()

    try:
        input_path = resolve_input(args.input)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    out_path = make_output_path(input_path)

    try:
        run_scraper(input_path, out_path)
    except SystemExit as e:
        sys.exit(e.code if isinstance(e, SystemExit) else 1)
    except Exception as e:
        print("Error running scraper:", str(e), file=sys.stderr)
        sys.exit(1)

    preview_file(out_path)


if __name__ == "__main__":
    main()
