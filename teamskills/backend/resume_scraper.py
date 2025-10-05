#!/usr/bin/env python3
"""
resume_scraper.py
Usage:
  python resume_scraper.py --input "/path/to/resume.pdf" --output "resume.txt" [--threshold 500]

Behavior:
- If input is a PDF: try pdfplumber first.
- If the result text length < threshold, use Google Cloud Vision OCR as fallback.
- If input is an image: use Google Cloud Vision directly.

Dependencies:
  pip install pdfplumber
  pip install google-cloud-vision pdf2image pillow   # for Vision OCR and PDF->image
System deps for PDF->image:
  - Poppler (required by pdf2image): choco install poppler  |  brew install poppler  |  apt-get install poppler-utils
Env:
  - GOOGLE_APPLICATION_CREDENTIALS must point to your service account JSON for Vision.
  $env:GOOGLE_APPLICATION_CREDENTIALS="teamskills\teamskills-474117-5ac11a782ba3.json" # or whatever it should be
"""

import argparse
import io
import os
import sys
from typing import List
import statistics
from collections import defaultdict
from typing import Optional
from .path_utils import cache_dir, teamskills_root


# --- Optional imports guarded at use-time ---
def _import_pdfplumber():
    try:
        import pdfplumber  # type: ignore
        return pdfplumber
    except Exception as e:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber") from e

def _import_vision_and_pdf2image():
    try:
        from google.cloud import vision  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "google-cloud-vision not installed or credentials missing. "
            "Run: pip install google-cloud-vision"
        ) from e
    try:
        from pdf2image import convert_from_bytes  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "pdf2image not installed. Run: pip install pdf2image pillow\n"
            "Also install Poppler: choco install poppler | brew install poppler | apt-get install poppler-utils"
        ) from e
    return vision, convert_from_bytes

# --- Extractors ---
def extract_with_pdfplumber(pdf_path: str) -> str:
    pdfplumber = _import_pdfplumber()
    text_parts: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            if t.strip():
                text_parts.append(t.strip())
    return "\n\n\f\n\n".join(text_parts).strip()  # add form-feed between pages


def generate_markdown_from_pdf(pdf_path: str) -> Optional[str]:
    """
    Heuristic Markdown generator using pdfplumber character metrics.
    Returns Markdown text when headings are detected; otherwise None.
    """
    pdfplumber = _import_pdfplumber()
    try:
        lines_info = []
        with pdfplumber.open(pdf_path) as pdf:
            for pnum, page in enumerate(pdf.pages):
                # Use page.extract_text() for line-level text to preserve spacing
                page_text = page.extract_text() or ""
                page_lines = [ln.rstrip() for ln in page_text.splitlines() if ln.strip()]
                if not page_lines:
                    continue

                # Group chars by rounded 'top' to compute font sizes per visual line
                chars = page.chars or []
                buckets: list[tuple[int, list]] = []
                if chars:
                    temp: dict[int, list] = defaultdict(list)
                    for ch in chars:
                        try:
                            y = int(round(float(ch.get("top", 0))))
                        except Exception:
                            y = 0
                        temp[y].append(ch)
                    buckets = sorted(temp.items(), key=lambda it: it[0])

                # If the number of visual buckets and extracted text lines differ a lot,
                # don't attempt mapping — fallback to None so we emit plaintext.
                if buckets and abs(len(buckets) - len(page_lines)) > max(2, int(len(page_lines) * 0.4)):
                    return None

                # Map lines (by order) to buckets (by order) when possible to get avg font sizes
                for idx, text in enumerate(page_lines):
                    avg_size = 0.0
                    fonts: list[str] = []
                    y = None
                    if buckets:
                        b_idx = min(idx, len(buckets) - 1)
                        y, chs = buckets[b_idx]
                        sizes = [float(c.get("size", 0)) for c in chs if c.get("size")]
                        avg_size = float(sum(sizes) / len(sizes)) if sizes else 0.0
                        fonts = [c.get("fontname", "") for c in chs]

                    lines_info.append({"page": pnum, "y": y or 0, "text": text, "avg_size": avg_size, "fonts": fonts})

        if not lines_info:
            return None

        sizes = [li["avg_size"] for li in lines_info if li["avg_size"] > 0]
        if not sizes:
            return None

        median = statistics.median(sizes)
        max_size = max(sizes)

        # If there's not a meaningful size difference, don't attempt markdown
        if median <= 0 or (max_size / median) < 1.15:
            return None

        md_lines: List[str] = []
        for li in lines_info:
            text = li["text"]
            avg = li["avg_size"]

            # simple list detection
            if text.startswith(("- ", "• ", "* ", "– ")) or (len(text) > 2 and text[0].isdigit() and text[1] in ").) "):
                md_lines.append(text)
                continue

            # heading heuristics: very large font -> H1 (name), large font -> H2
            if avg >= (median + (max_size - median) * 0.6):
                # if this line is the absolute largest font (e.g. candidate name), use H1
                if abs(avg - max_size) < 1e-6 or avg >= max_size - 0.5:
                    md_lines.append(f"# {text}")
                else:
                    md_lines.append(f"## {text}")
            else:
                md_lines.append(text)

        # ensure we have at least one heading for this to be considered Markdown
        if not any(l.startswith("#") for l in md_lines):
            return None

        # Join with double newlines to separate blocks
        return "\n\n".join(md_lines)
    except Exception:
        return None

def extract_with_gcv(input_path: str) -> str:
    """
    Uses Google Cloud Vision OCR.
    - If input is PDF: render pages to images (via pdf2image) then OCR each page.
    - If input is image: OCR directly.
    """
    vision, convert_from_bytes = _import_vision_and_pdf2image()
    client = vision.ImageAnnotatorClient()

    ext = os.path.splitext(input_path)[1].lower()
    is_pdf = ext == ".pdf"

    try:
        with open(input_path, "rb") as f:
            content = f.read()
    except Exception as e:
        raise RuntimeError(f"Could not read file: {input_path}") from e

    texts: List[str] = []

    if is_pdf:
        try:
            pages = convert_from_bytes(content)  # requires Poppler
        except Exception as e:
            raise RuntimeError(
                "Failed to convert PDF to images (pdf2image/poppler). See install notes."
            ) from e
        for im in pages:
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            image = vision.Image(content=buf.getvalue())
            resp = client.document_text_detection(image=image)
            if resp.error.message:
                raise RuntimeError(f"Vision error: {resp.error.message}")
            if resp.full_text_annotation and resp.full_text_annotation.text:
                texts.append(resp.full_text_annotation.text.strip())
    else:
        # assume it is an image (png/jpg/jpeg/tiff)
        image = vision.Image(content=content)
        resp = client.document_text_detection(image=image)
        if resp.error.message:
            raise RuntimeError(f"Vision error: {resp.error.message}")
        if resp.full_text_annotation and resp.full_text_annotation.text:
            texts.append(resp.full_text_annotation.text.strip())

    return "\n\n\f\n\n".join([t for t in texts if t]).strip()

# --- Main ---
def main():
    ap = argparse.ArgumentParser(description="Scrape resume text with pdfplumber → fallback to Google Vision OCR")
    ap.add_argument("--input", required=True, help="Path to resume file (PDF or image)")
    ap.add_argument("--output", required=True, help="Path to write extracted text (.txt)")
    ap.add_argument("--threshold", type=int, default=500,
                    help="If initial extracted text length < threshold, fall back to Vision OCR (default: 500)")
    args = ap.parse_args()

    in_path = args.input
    out_path = args.output
    threshold = args.threshold

    if not os.path.exists(in_path):
        print(f"ERROR: Input path does not exist: {in_path}", file=sys.stderr)
        sys.exit(2)

    ext = os.path.splitext(in_path)[1].lower()

    extracted = ""
    used = ""

    try:
        if ext == ".pdf":
            # 1) Try pdfplumber first
            extracted = extract_with_pdfplumber(in_path)
            used = "pdfplumber"
        else:
            # For images, go straight to Vision
            extracted = ""
            used = "none"

        # 2) If short or empty, try Vision OCR
        if len(extracted) < threshold:
            gcv_text = extract_with_gcv(in_path)
            if len(gcv_text) > len(extracted):
                extracted = gcv_text
                used = "vision"
    except Exception as e:
        # If pdfplumber fails, try Vision as a last resort
        if ext == ".pdf":
            try:
                gcv_text = extract_with_gcv(in_path)
                if gcv_text:
                    extracted = gcv_text
                    used = "vision (fallback after error)"
                else:
                    raise
            except Exception as e2:
                print(f"ERROR: Extraction failed. pdfplumber error: {e}\nVision error: {e2}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"ERROR: Extraction failed: {e}", file=sys.stderr)
            sys.exit(1)

    # Write a simple plaintext report (.txt) preserving extracted spacing
    try:
        # Always write reports under teamskills/.cache/resumes
        cache_reports = str(cache_dir("resumes"))
        target_out = os.path.join(cache_reports, os.path.basename(out_path))

        # ensure .txt extension
        if target_out.endswith(".md") or target_out.endswith(".txt"):
            base = os.path.splitext(target_out)[0]
        else:
            base = target_out
        target_out = base + ".txt"

        with open(target_out, "w", encoding="utf-8") as f:
            f.write(f"Source file: {in_path}\n")
            f.write(f"Extractor used: {used}\n")
            f.write(f"Chars extracted: {len(extracted)}\n\n")
            f.write(extracted or "")

        out_path = target_out
    except Exception as e:
        print(f"ERROR: Could not write output file: {out_path} ({e})", file=sys.stderr)
        sys.exit(1)

    # Save original upload for traceability in teamskills/.cache/resumes
    try:
        # Save uploads at teamskills root in `.cache/resumes`
        uploads_dir = str(cache_dir("resumes"))
        os.makedirs(uploads_dir, exist_ok=True)
        base = os.path.basename(in_path)
        dst = os.path.join(uploads_dir, base)
        # only copy if not already present
        if not os.path.exists(dst):
            with open(in_path, "rb") as rf, open(dst, "wb") as wf:
                wf.write(rf.read())
    except Exception:
        pass

    print(f"OK: wrote {len(extracted)} chars to '{out_path}' using {used}.")


if __name__ == "__main__":
    main()
