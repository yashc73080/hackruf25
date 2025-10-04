#!/usr/bin/env python3
"""
Resume Ingestor (Local File → JSON → optional MongoDB)
- Reads a local PDF resume file
- Extracts text (pdfplumber; optional OCR fallback)
- Splits into sections (Education / Experience / Skills, etc.)
- Parses each section into structured JSON
- Prints JSON or saves to a file; optionally inserts into MongoDB

Usage:
  python resume_ingest_local.py /path/to/resume.pdf \
      --json-out parsed.json \
      --use-ocr                     # try OCR fallback if needed
      --mongo "mongodb://localhost:27017" --db skillsync --collection candidates

Dependencies:
  pip install pdfplumber python-dateutil
  # optional OCR fallback:
  pip install pytesseract pillow pdf2image
  # optional DB:
  pip install pymongo

Note: For OCR fallback (pdf2image), you may need system poppler.
"""

import argparse
import datetime
import io
import json
import re
from typing import Dict, List, Optional

# core deps
import pdfplumber
from dateutil import parser as dateparse

# optional deps guarded at use-time
try:
    from pymongo import MongoClient, ASCENDING  # type: ignore
except Exception:
    MongoClient = None  # type: ignore
    ASCENDING = 1  # dummy

# -----------------------------
# Config / Taxonomies
# -----------------------------
SKILL_TAXONOMY = {
    "python": {"python", "py"},
    "javascript": {"javascript", "js"},
    "typescript": {"typescript", "ts"},
    "react": {"react", "reactjs", "react.js"},
    "node": {"node", "nodejs", "node.js"},
    "java": {"java"},
    "c++": {"c++", "cpp"},
    "c": {"c"},
    "matlab": {"matlab"},
    "aws": {"aws", "amazon web services"},
    "gcp": {"gcp", "google cloud"},
    "azure": {"azure"},
    "tensorflow": {"tensorflow", "tf"},
    "pytorch": {"pytorch", "torch"},
    "sql": {"sql", "postgres", "mysql", "sqlite"},
    "html": {"html"},
    "css": {"css", "tailwind", "bootstrap"},
    "docker": {"docker"},
    "kubernetes": {"kubernetes", "k8s"},
    "git": {"git", "github", "gitlab"},
}

HEADER_ALIASES = {
    "education": {"education", "academics", "academic background"},
    "experience": {"experience", "work experience", "professional experience", "employment"},
    "skills": {"skills", "technical skills", "technologies", "toolbox"},
    "projects": {"projects", "selected projects"},
    "certifications": {"certifications", "certificates", "licenses"},
    "publications": {"publications", "papers"},
    "awards": {"awards", "achievements", "honors"},
    "summary": {"summary", "objective", "profile"},
}

SECTION_BULLET = re.compile(r"^\s*[-•\u2022\u25CF\u25AA]\s+")
DATE_RANGE = re.compile(
    r"(?P<start>(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s?\d{4}|\d{4})\s*[-–—]\s*(?P<end>(Present|Current|Now|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s?\d{4}|\d{4}))",
    re.IGNORECASE,
)
DEGREE_PAT = re.compile(r"(B\.?S\.?|BSc|Bachelor|M\.?S\.?|MSc|Master|Ph\.?D\.?|PhD|B\.?Tech|B\.?E\.?)", re.IGNORECASE)
GPA_PAT = re.compile(r"GPA[:\s]+([0-4]\.\d{1,2}|\d\.\d{1,2})", re.IGNORECASE)

# -----------------------------
# PDF Text Extraction
# -----------------------------

def extract_text_pdf_bytes(content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        texts = []
        for p in pdf.pages:
            t = p.extract_text() or ""
            texts.append(t)
        return "\n".join(texts).strip()


def ocr_pdf_bytes(content: bytes) -> str:
    """OCR fallback for scanned PDFs. Requires pdf2image + pytesseract."""
    try:
        from pdf2image import convert_from_bytes  # type: ignore
        import pytesseract  # type: ignore
    except Exception:
        return ""
    pages = convert_from_bytes(content)
    return "\n".join(pytesseract.image_to_string(im) for im in pages)

# -----------------------------
# Sectioning / Parsing
# -----------------------------

def find_headers(lines: List[str]) -> List[int]:
    idxs = []
    for i, line in enumerate(lines):
        raw = line.strip()
        lower = raw.lower().strip(":")
        if any(lower in v for v in HEADER_ALIASES.values()):
            idxs.append(i)
            continue
        # heuristic header: ALL CAPS short line or title-like with colon
        if (raw.isupper() and 3 <= len(raw) <= 40) or re.match(r"^[A-Za-z &/]{3,}:\s*$", raw):
            idxs.append(i)
    return sorted(set(idxs))


def label_header(text: str) -> str:
    lower = text.lower().strip(": ")
    for label, aliases in HEADER_ALIASES.items():
        if lower in aliases:
            return label
    return lower


def split_sections(full_text: str) -> Dict[str, str]:
    lines = full_text.splitlines()
    hdr_idx = find_headers(lines)
    if not hdr_idx:
        return {"unknown": full_text}
    hdr_idx.append(len(lines))
    sections: Dict[str, str] = {}
    for a, b in zip(hdr_idx, hdr_idx[1:]):
        header = label_header(lines[a])
        body = "\n".join(lines[a + 1 : b]).strip()
        sections[header] = (sections.get(header, "") + ("\n" if header in sections else "") + body).strip()
    return sections


def norm_date(s: str) -> Optional[str]:
    s = s.replace("–", "-").replace("—", "-").replace("to", "-")
    s = re.sub(r"\b(Present|Current|Now)\b", "", s, flags=re.I).strip()
    if not s:
        return None
    try:
        d = dateparse.parse(s, default=datetime.datetime(2000, 1, 1))
        return d.date().isoformat()
    except Exception:
        return None


def parse_education(text: str) -> List[dict]:
    if not text:
        return []
    blocks = re.split(r"\n\s*\n", text.strip())
    out: List[dict] = []
    for b in blocks:
        line = " ".join(l.strip() for l in b.splitlines())
        degree = None; major = None; inst = None; gpa = None; sdate = None; edate = None
        m = DEGREE_PAT.search(line)
        if m:
            degree = m.group(1).upper().replace(".", "")
        inst_match = re.search(r"\b(University|College|Institute|School|Polytechnic|Rutgers[a-zA-Z ,]*)\b", line, re.I)
        if inst_match:
            inst = inst_match.group(0)
        maj_match = re.search(
            r"(Computer Science|Electrical( and)? Computer Engineering|Data Science|Mathematics|Physics|Statistics|Mechanical Engineering|Aerospace|Information Technology)",
            line,
            re.I,
        )
        if maj_match:
            major = maj_match.group(0)
        g = GPA_PAT.search(line)
        if g:
            try:
                gpa = float(g.group(1))
            except Exception:
                pass
        dr = DATE_RANGE.search(line)
        if dr:
            sdate = norm_date(dr.group("start"))
            edate = norm_date(dr.group("end"))
        entry = {
            "institution": inst,
            "degree": degree,
            "major": major,
            "start_date": sdate,
            "end_date": edate,
            "gpa": gpa,
            "raw": line,
        }
        if any([inst, degree, major]):
            out.append(entry)
    return out


def parse_experience(text: str) -> List[dict]:
    if not text:
        return []
    lines = [l for l in text.splitlines() if l.strip()]
    entries: List[dict] = []
    cur = {"company": None, "title": None, "location": None, "start_date": None, "end_date": None, "bullets": [], "tech": []}
    for i, l in enumerate(lines):
        line = l.strip().replace("—", "-")
        if DATE_RANGE.search(line) or ("@" in line) or (i == 0):
            if cur["company"] or cur["title"] or cur["bullets"]:
                entries.append(cur)
                cur = {"company": None, "title": None, "location": None, "start_date": None, "end_date": None, "bullets": [], "tech": []}
            if "@" in line:
                parts = [p.strip() for p in line.split("@", 1)]
                cur["title"] = parts[0]
                cur["company"] = parts[1]
            else:
                parts = [p.strip() for p in re.split(r"[-–—]\s*", line, maxsplit=1)]
                if len(parts) == 2:
                    if re.search(r"(Inc\.?|LLC|Labs|University|Corp\.?)", parts[0], re.I):
                        cur["company"], cur["title"] = parts[0], parts[1]
                    else:
                        cur["title"], cur["company"] = parts[0], parts[1]
                else:
                    cur["title"] = line
            m = DATE_RANGE.search(line)
            if m:
                cur["start_date"] = norm_date(m.group("start"))
                cur["end_date"] = norm_date(m.group("end"))
        elif SECTION_BULLET.match(line):
            cur["bullets"].append(re.sub(SECTION_BULLET, "", line).strip())
        else:
            if re.search(r"[A-Za-z]+,\s*[A-Z]{2}\b", line):
                cur["location"] = line
            else:
                for canon, aliases in SKILL_TAXONOMY.items():
                    for a in aliases:
                        if re.search(rf"\\b{re.escape(a)}\\b", line, re.I):
                            cur["tech"].append(canon)
    if cur["company"] or cur["title"] or cur["bullets"]:
        entries.append(cur)
    for e in entries:
        e["tech"] = sorted(set(e["tech"]))
    return entries


def canonicalize_skill(token: str) -> Optional[dict]:
    t = token.strip().lower()
    if not t:
        return None
    for canon, aliases in SKILL_TAXONOMY.items():
        if t in aliases:
            return {"canonical": canon, "aliases": [token]}
    return {"canonical": t, "aliases": [token]}


def parse_skills(text: str) -> List[dict]:
    if not text:
        return []
    raw = re.split(r"[,;/|•\u2022]\s*", text.replace("\n", " ").strip())
    skills = []
    for tok in raw:
        c = canonicalize_skill(tok)
        if c:
            skills.append(c)
    merged: Dict[str, dict] = {}
    for s in skills:
        k = s["canonical"]
        merged.setdefault(k, {"canonical": k, "aliases": []})
        merged[k]["aliases"].extend(s["aliases"])
    for v in merged.values():
        v["aliases"] = sorted(set(v["aliases"]))
    return sorted(merged.values(), key=lambda x: x["canonical"])


def parse_contact_name(full_text: str) -> dict:
    first_line = full_text.splitlines()[0].strip() if full_text.splitlines() else None
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", full_text)
    phone_match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", full_text)
    loc_match = re.search(r"[A-Za-z .'-]+,\s*[A-Z]{2}\b", full_text)
    name = first_line if first_line and len(first_line.split()) <= 6 else None
    return {
        "name": name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "location": loc_match.group(0) if loc_match else None,
    }

# -----------------------------
# Mongo helpers (optional)
# -----------------------------

def maybe_insert_mongo(doc: dict, mongo_uri: Optional[str], db_name: Optional[str], coll_name: Optional[str]) -> Optional[str]:
    if not mongo_uri or not db_name or not coll_name:
        return None
    if MongoClient is None:
        raise RuntimeError("pymongo not installed. pip install pymongo")
    client = MongoClient(mongo_uri)
    coll = client[db_name][coll_name]
    try:
        coll.create_index([("skills.canonical", ASCENDING)])
        coll.create_index([("experience.company", ASCENDING)])
        coll.create_index([("name", ASCENDING)])
    except Exception:
        pass
    res = coll.insert_one(doc)
    return str(res.inserted_id)

# -----------------------------
# Main
# -----------------------------

def main():
    ap = argparse.ArgumentParser(description="Local PDF resume → JSON → optional MongoDB")
    ap.add_argument("pdf_path", help="Path to local PDF resume")
    ap.add_argument("--json-out", help="Path to write JSON output", default=None)
    ap.add_argument("--use-ocr", action="store_true", help="Try OCR fallback if text is sparse")
    ap.add_argument("--mongo", help="MongoDB URI (optional)", default=None)
    ap.add_argument("--db", help="Mongo database name (optional)", default=None)
    ap.add_argument("--collection", help="Mongo collection name (optional)", default=None)
    args = ap.parse_args()

    # read file bytes
    with open(args.pdf_path, "rb") as f:
        content = f.read()

    text = extract_text_pdf_bytes(content)
    if args.use_ocr and len(text) < 200:
        ocr_text = ocr_pdf_bytes(content)
        if len(ocr_text) > len(text):
            text = ocr_text

    if not text:
        raise SystemExit("ERROR: Could not extract any text from PDF. Try --use-ocr.")

    sections = split_sections(text)
    contact = parse_contact_name(text)

    education = parse_education(sections.get("education", ""))
    experience = parse_experience(sections.get("experience", ""))
    skills = parse_skills(sections.get("skills", ""))

    doc = {
        "name": contact.get("name"),
        "contact": {
            "email": contact.get("email"),
            "phone": contact.get("phone"),
            "location": contact.get("location"),
        },
        "education": education,
        "experience": experience,
        "skills": skills,
        "source": {
            "filename": args.pdf_path.split("/")[-1],
            "ingested_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "raw_sections": {k: v[:4000] for k, v in sections.items()},
    }

    # optional Mongo insert
    inserted_id = maybe_insert_mongo(doc, args.mongo, args.db, args.collection)
    if inserted_id:
        doc["_mongo_id"] = inserted_id

    # print pretty JSON
    print(json.dumps(doc, indent=2, ensure_ascii=False))

    # write JSON to file
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        print(f"\nWrote JSON → {args.json_out}")


if __name__ == "__main__":
    main()
