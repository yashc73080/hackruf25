# app.py
import os, sys, json, uuid, re, tempfile, subprocess
from typing import List, Optional

from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ---------------- import skill extractor ----------------
try:
    from skill_extractor import analyze_profile
except Exception as e:
    print(f"Warning: Could not import skill_extractor: {e}")
    analyze_profile = None

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

# ---------------- helpers: GitHub ----------------
def parse_github_username(url: Optional[str]) -> Optional[str]:
    if not url: return None
    m = re.search(r"github\.com/([^/\s]+)", url.strip())
    return m.group(1) if m else None

# ---------------- helpers: Skill Extraction ----------------
def run_skill_extraction(github_url: Optional[str] = None, resume_path: Optional[str] = None) -> dict:
    """
    Uses the new skill_extractor.py to analyze GitHub and/or resume.
    Returns: {"languages":[...], "skills":[...], "keywords":[...]}
    """
    result = {"languages": [], "skills": [], "keywords": []}
    
    if not analyze_profile:
        print("Skill extractor not available")
        return result

    # Extract GitHub username if URL provided
    github_username = None
    if github_url:
        github_username = parse_github_username(github_url)
    
    # Skip if neither source is available
    if not github_username and not resume_path:
        return result

    try:
        print(f"Running skill extraction - GitHub: {github_username}, Resume: {resume_path}")
        analysis_result = analyze_profile(
            github_username=github_username,
            resume_path=resume_path
        )
        
        # Extract skills from the analysis result
        all_skills = set()
        all_languages = set()
        all_keywords = set()
        
        # Process GitHub analysis
        github_analysis = analysis_result.get("github_analysis", {})
        if github_analysis and "error" not in github_analysis:
            # Add languages from GitHub
            all_languages.update(github_analysis.get("languages", []))
            # Add frameworks and tools as skills
            all_skills.update(github_analysis.get("frameworks", []))
            all_skills.update(github_analysis.get("tools", []))
            # Add concepts and domains as keywords
            all_keywords.update(github_analysis.get("concepts", []))
            all_keywords.update(github_analysis.get("domains", []))
        
        # Process resume analysis
        resume_analysis = analysis_result.get("resume_analysis", {})
        if resume_analysis and "error" not in resume_analysis:
            # Add technical skills and languages
            all_skills.update(resume_analysis.get("technical_skills", []))
            all_skills.update(resume_analysis.get("soft_skills", []))
            # Add domains and certifications as keywords
            all_keywords.update(resume_analysis.get("domains", []))
            all_keywords.update(resume_analysis.get("certifications", []))
            all_keywords.update(resume_analysis.get("experience_keywords", []))
        
        # Process combined analysis if available
        combined_analysis = analysis_result.get("combined_skills", {})
        if combined_analysis and "error" not in combined_analysis:
            all_skills.update(combined_analysis.get("technical_skills", []))
            all_skills.update(combined_analysis.get("soft_skills", []))
            all_keywords.update(combined_analysis.get("domains", []))
            all_keywords.update(combined_analysis.get("certifications", []))
            all_keywords.update(combined_analysis.get("keywords", []))
        
        # Separate programming languages from skills
        prog_langs = {
            "python", "java", "javascript", "typescript", "c", "c++", "c#", "go", "rust",
            "matlab", "sql", "r", "scala", "html", "css", "bash", "shell", "powershell",
            "php", "ruby", "swift", "kotlin", "dart", "perl", "lua", "haskell", "clojure",
            "f#", "pascal", "cobol", "fortran", "assembly", "vb.net", "objective-c"
        }
        
        # Extract languages from skills and add to languages set
        for skill in list(all_skills):
            if skill.lower() in prog_langs:
                all_languages.add(skill)
                all_skills.discard(skill)  # Remove from skills since it's a language
        
        result = {
            "languages": norm_list(list(all_languages)),
            "skills": norm_list(list(all_skills)),
            "keywords": norm_list(list(all_keywords))
        }
        
        print(f"Skill extraction completed: {len(result['languages'])} languages, {len(result['skills'])} skills, {len(result['keywords'])} keywords")
        
    except Exception as e:
        print(f"Error in skill extraction: {e}")
        import traceback
        traceback.print_exc()
    
    return result

# ---------------- FastAPI app ----------------
app = FastAPI(title="Team Member Store")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# serve uploaded PDFs
app.mount("/resumes", StaticFiles(directory=UPLOAD_DIR), name="resumes")

@app.post("/api/process-team-data")
async def process_team_data(
    specifications: str = Form(...),
    teamMembersCount: int = Form(...),
    **form_data
):
    """
    Process team data from TeamInputForm.jsx
    Expects: specifications, teamMembersCount, and member_X_* fields
    """
    print("=" * 50)
    print("🚀 RECEIVED DATA AT /api/process-team-data")
    print("=" * 50)
    
    print(f"📊 Team Members Count: {teamMembersCount}")
    print(f"📝 Specifications (raw): {specifications}")
    
    print("\n📦 ALL FORM DATA RECEIVED:")
    for key, value in form_data.items():
        if hasattr(value, 'filename'):
            print(f"  {key}: [FILE] {value.filename} ({value.content_type})")
        else:
            print(f"  {key}: {value}")
    
    print("\n🔍 PARSED TEAM MEMBERS:")
    for i in range(teamMembersCount):
        print(f"\n  Member {i}:")
        name = form_data.get(f'member_{i}_name')
        github = form_data.get(f'member_{i}_githubUsername', '')
        resume = form_data.get(f'member_{i}_resumeFile')
        
        print(f"    Name: '{name}'")
        print(f"    GitHub: '{github}'")
        if resume and hasattr(resume, 'filename'):
            print(f"    Resume: {resume.filename} ({resume.content_type}, {getattr(resume, 'size', 'unknown size')})")
        else:
            print(f"    Resume: {resume}")
    
    try:
        specs = json.loads(specifications)
        print(f"\n📋 Parsed Specifications: {json.dumps(specs, indent=2)}")
    except Exception as e:
        print(f"\n❌ Failed to parse specifications: {e}")
        specs = {}
    
    print("=" * 50)
    
    # Rest of your existing processing logic...
    try:
        # Extract team members from form data
        processed_members = []
        db = load_db()
        
        for i in range(teamMembersCount):
            print(f"\n--- Processing Member {i+1} ---")
            
            # Extract member data from form
            member_name = form_data.get(f'member_{i}_name')
            member_github = form_data.get(f'member_{i}_githubUsername', '')
            member_resume = form_data.get(f'member_{i}_resumeFile')
            
            print(f"Name: {member_name}")
            print(f"GitHub: {member_github}")
            print(f"Resume file: {getattr(member_resume, 'filename', 'None') if member_resume else 'None'}")
            
            if not member_name:
                print("Skipping member - no name provided")
                continue
                
            # Find or create member
            members = db["members"]
            m = find_by_name(members, member_name)
            if not m:
                print("Creating new member")
                m = {
                    "member_id": str(uuid.uuid4()),
                    "name": member_name.strip(),
                    "github_url": f"https://github.com/{member_github}" if member_github else None,
                    "resume_path": None,
                    "skills": [],
                    "keywords": [],
                    "languages": []
                }
                members.append(m)
            else:
                print("Updating existing member")
                if member_github:
                    m["github_url"] = f"https://github.com/{member_github}"

            # Save resume file if provided
            resume_path = None
            if member_resume and hasattr(member_resume, 'read'):
                ext = os.path.splitext(getattr(member_resume, 'filename', 'resume.pdf'))[1] or ".pdf"
                dest = os.path.join(UPLOAD_DIR, f"{m['member_id']}{ext}")
                
                print(f"Saving resume to: {dest}")
                # Read file content
                content = await member_resume.read()
                with open(dest, "wb") as f:
                    f.write(content)
                m["resume_path"] = dest
                resume_path = dest

            # Run skill extraction using the new unified approach
            print("Running skill extraction...")
            skill_results = run_skill_extraction(
                github_url=m.get("github_url"),
                resume_path=resume_path or m.get("resume_path")
            )
            print(f"Skill extraction results: {skill_results}")

            # Merge + dedupe with existing data
            m["languages"] = norm_list((m.get("languages") or []) + (skill_results.get("languages") or []))
            m["skills"]     = norm_list((m.get("skills") or []) + (skill_results.get("skills") or []))
            m["keywords"]   = norm_list((m.get("keywords") or []) + (skill_results.get("keywords") or []))

            print(f"Final member data: {m}")
            processed_members.append(m)

        # Save updated database
        save_db(db)
        print(f"\n✅ SAVED {len(processed_members)} MEMBERS TO DB")

        return {
            "success": True,
            "data": {
                "specifications": specs,
                "processed_members": processed_members,
                "total_members": len(processed_members)
            }
        }

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"success": False, "error": str(e)}, 
            status_code=500
        )

@app.post("/member")
async def create_or_update_member(
    name: str = Form(...),
    github_url: str = Form(""),
    resume_file: UploadFile | None = None
):
    """
    Create/update by NAME, store GitHub URL, save PDF, run skill extraction, and persist.
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

    # run skill extraction
    skill_results = run_skill_extraction(
        github_url=m.get("github_url"),
        resume_path=m.get("resume_path")
    )

    # merge + dedupe
    m["languages"] = norm_list((m.get("languages") or []) + (skill_results.get("languages") or []))
    m["skills"]     = norm_list((m.get("skills") or []) + (skill_results.get("skills") or []))
    m["keywords"]   = norm_list((m.get("keywords") or []) + (skill_results.get("keywords") or []))

    save_db(db)
    return {"ok": True, "member": m}

@app.post("/member/skills")
async def add_skills(
    name: str,
    skills: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    languages: Optional[List[str]] = None
):
    """Optional: push skills later if needed."""
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
    """Re-run skill extraction for an existing member (no re-upload needed)."""
    db = load_db()
    m = find_by_name(db["members"], name)
    if not m:
        return JSONResponse({"ok": False, "error": "member not found"}, status_code=404)

    skill_results = run_skill_extraction(
        github_url=m.get("github_url"),
        resume_path=m.get("resume_path")
    )

    # Replace existing skills instead of merging for rescrape
    m["languages"] = skill_results.get("languages", [])
    m["skills"]    = skill_results.get("skills", [])
    m["keywords"]  = skill_results.get("keywords", [])

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
    