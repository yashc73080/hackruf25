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

    # Write output
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(extracted or "")
    except Exception as e:
        print(f"ERROR: Could not write output file: {out_path} ({e})", file=sys.stderr)
        sys.exit(1)

    print(f"OK: wrote {len(extracted)} chars to '{out_path}' using {used}.")


if __name__ == "__main__":
    main()
