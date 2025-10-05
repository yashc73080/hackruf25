# app.py
import os, sys, json, uuid, re, tempfile, subprocess
from typing import List, Optional

from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ---------------- paths & storage ----------------
DB_PATH = "team_members.json"
UPLOAD_DIR = "resumes"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def load_db():
    if not os.path.exists(DB_PATH):
        return {"members": []}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def find_by_name(members, name: str):
    n = (name or "").strip().lower()
    return next((m for m in members if (m.get("name","").strip().lower() == n)), None)

def norm_list(items: Optional[List[str]]) -> List[str]:
    out, seen = [], set()
    for s in items or []:
        val = (s or "").strip()
        key = val.lower()
        if val and key not in seen:
            seen.add(key)
            out.append(val)
    return out

# ---------------- import your scrapers ----------------
try:
    import github_scraper as gh  # your module in same folder
except Exception:
    gh = None

# ---------------- helpers: GitHub ----------------
def parse_github_username(url: Optional[str]) -> Optional[str]:
    if not url: return None
    m = re.search(r"github\.com/([^/\s]+)", url.strip())
    return m.group(1) if m else None

def run_github_scraper(github_url: Optional[str]) -> dict:
    """
    Returns: {"languages":[...], "skills":[...], "keywords":[...]}
    Uses your github_scraper.py if available.
    """
    result = {"languages": [], "skills": [], "keywords": []}
    if not github_url or not gh:
        return result

    username = parse_github_username(github_url)
    if not username:
        return result

    try:
        if hasattr(gh, "summarize_user"):
            data = gh.summarize_user(username) or {}
            langs = [item["name"] for item in data.get("overall_language_percentages", [])]
            result["languages"] = list(dict.fromkeys(langs))

            # try optional keywords from top READMEs if your module has it
            if hasattr(gh, "extract_keywords_from_top_readmes"):
                kws = gh.extract_keywords_from_top_readmes(username, top=3) or []
                result["keywords"] = list(dict.fromkeys(kws))
            elif hasattr(gh, "get_keywords"):
                kws = gh.get_keywords(username) or []
                result["keywords"] = list(dict.fromkeys(kws))

        elif hasattr(gh, "scrape"):
            payload = gh.scrape(github_url) or {}
            for k in ("languages", "skills", "keywords"):
                if payload.get(k):
                    result[k] = list(dict.fromkeys(payload[k]))
    except Exception:
        # don't crash the request if GH scraping fails
        pass

    return result

# ---------------- helpers: Resume (call your CLI) ----------------
def run_resume_scraper_via_cli(resume_path: Optional[str]) -> dict:
    """
    Calls your resume_scraper.py as a subprocess:
      python resume_scraper.py --input <pdf> --output <tmp.md> --threshold 999999
    Parses the markdown's "## Extracted Skills" bullets.
    Returns: {"languages":[...], "skills":[...], "keywords":[...]}
    """
    if not resume_path or not os.path.exists(resume_path):
        return {"languages": [], "skills": [], "keywords": []}

    # temp output for your CLI markdown report
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
        out_path = tmp.name

    try:
        cmd = [sys.executable, "resume_scraper.py",
               "--input", resume_path, "--output", out_path, "--threshold", "999999"]
        subprocess.run(cmd, check=True)

        with open(out_path, "r", encoding="utf-8") as f:
            md = f.read()

        # parse "## Extracted Skills" block: lines like "- `skill`"
        skills = []
        m = re.search(r"## Extracted Skills(.*?)(?:\n##|\Z)", md, flags=re.S|re.I)
        block = m.group(1) if m else ""
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("- `") and line.endswith("`"):
                skills.append(line[3:-1])

        # derive languages from skills list (basic set; adjust if you want)
        prog_langs = {
            "python","java","javascript","typescript","c","c++","c#","go","rust",
            "matlab","sql","r","scala","html","css","bash","shell","powershell"
        }
        langs = sorted({s.lower() for s in skills if s.lower() in prog_langs})

        # unique while preserving order
        skills_unique = list(dict.fromkeys(skills))
        keywords = skills_unique  # mirror for now

        return {
            "languages": langs,
            "skills": skills_unique,
            "keywords": keywords
        }
    except Exception:
        return {"languages": [], "skills": [], "keywords": []}
    finally:
        try: os.remove(out_path)
        except Exception: pass

# ---------------- FastAPI app ----------------
app = FastAPI(title="Team Member Store")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# serve uploaded PDFs
app.mount("/resumes", StaticFiles(directory=UPLOAD_DIR), name="resumes")

@app.post("/member")
async def create_or_update_member(
    name: str = Form(...),
    github_url: str = Form(""),
    resume_file: UploadFile | None = None
):
    """
    Create/update by NAME, store GitHub URL, save PDF, run scrapers, and persist.
    """
    db = load_db()
    members = db["members"]

    m = find_by_name(members, name)
    if not m:
        m = {
            "member_id": str(uuid.uuid4()),
            "name": name.strip(),
            "github_url": github_url or None,
            "resume_path": None,
            "skills": [],
            "keywords": [],
            "languages": []
        }
        members.append(m)
    else:
        if github_url:
            m["github_url"] = github_url

    # save/replace resume as resumes/{member_id}.pdf (keep original extension)
    if resume_file:
        ext = os.path.splitext(resume_file.filename)[1] or ".pdf"
        dest = os.path.join(UPLOAD_DIR, f"{m['member_id']}{ext}")
        with open(dest, "wb") as f:
            f.write(await resume_file.read())
        m["resume_path"] = dest

    # run scrapers
    gh_res = run_github_scraper(m.get("github_url"))
    cv_res = run_resume_scraper_via_cli(m.get("resume_path"))

    # merge + dedupe
    m["languages"] = norm_list((m.get("languages") or []) + (gh_res.get("languages") or []) + (cv_res.get("languages") or []))
    m["skills"]     = norm_list((m.get("skills") or []) + (gh_res.get("skills") or []) + (cv_res.get("skills") or []))
    m["keywords"]   = norm_list((m.get("keywords") or []) + (gh_res.get("keywords") or []) + (cv_res.get("keywords") or []))

    save_db(db)
    return {"ok": True, "member": m}

@app.post("/member/skills")
async def add_skills(
    name: str,
    skills: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    languages: Optional[List[str]] = None
):
    """Optional: push skills later if your scrapers run elsewhere."""
    db = load_db()
    members = db["members"]
    m = find_by_name(members, name)
    if not m:
        return JSONResponse({"ok": False, "error": "member not found"}, status_code=404)

    m["skills"]   = norm_list((m.get("skills") or []) + (skills or []))
    m["keywords"] = norm_list((m.get("keywords") or []) + (keywords or []))
    m["languages"]= norm_list((m.get("languages") or []) + (languages or []))

    save_db(db)
    return {"ok": True, "member": m}

@app.post("/member/rescrape")
def rescrape_member(name: str):
    """Re-run scrapers for an existing member (no re-upload needed)."""
    db = load_db()
    m = find_by_name(db["members"], name)
    if not m:
        return JSONResponse({"ok": False, "error": "member not found"}, status_code=404)

    gh_res = run_github_scraper(m.get("github_url"))
    cv_res = run_resume_scraper_via_cli(m.get("resume_path"))

    m["languages"] = norm_list((m.get("languages") or []) + (gh_res.get("languages") or []) + (cv_res.get("languages") or []))
    m["skills"]     = norm_list((m.get("skills") or []) + (gh_res.get("skills") or []) + (cv_res.get("skills") or []))
    m["keywords"]   = norm_list((m.get("keywords") or []) + (gh_res.get("keywords") or []) + (cv_res.get("keywords") or []))

    save_db(db)
    return {"ok": True, "member": m}

@app.get("/members")
def list_members():
    return {"ok": True, "members": load_db()["members"]}

@app.get("/member")
def get_member(name: str):
    db = load_db()
    m = find_by_name(db["members"], name)
    if not m:
        return JSONResponse({"ok": False, "error": "member not found"}, status_code=404)
    return {"ok": True, "member": m}