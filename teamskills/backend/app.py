# app.py
import os, sys, json, uuid, re, tempfile, subprocess
from typing import List, Optional

from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- Imports for Role Matching ---
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

# ---------------- import skill extractor ----------------
try:
    from skill_extractor import analyze_profile
except Exception as e:
    print(f"Warning: Could not import skill_extractor: {e}")
    analyze_profile = None

# --- Load environment variables and configure Gemini ---
load_dotenv()
# Also try loading from parent directory
parent_dir = os.path.dirname(os.path.dirname(__file__))
env_local_path = os.path.join(parent_dir, '.env.local')
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)

import google.generativeai as genai

# --- Configure Gemini client ---
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    # Handle the case where the API key is not found
    print("GEMINI_API_KEY not found.")
    genai_configured = False
else:
    genai.configure(api_key=api_key)
    genai_configured = True


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

# --- Helper: get embedding from Gemini ---
def get_embedding(text: str) -> np.ndarray:
    """
    Uses Gemini embedding model to vectorize a string semantically.
    """
    if not genai_configured:
        raise RuntimeError("Gemini API key not configured.")
    response = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="semantic_similarity"
    )
    return np.array(response["embedding"], dtype=np.float32)

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
    try:
        specs = json.loads(specifications)
        roles = {spec.get("title", f"Role {i+1}"): spec.get("description", "") for i, spec in enumerate(specs)}
    except (json.JSONDecodeError, AttributeError):
        roles = {"Default Role": "A generalist role for this project"}


    try:
        # Extract team members from form data
        processed_members = []
        db = load_db()

        for i in range(teamMembersCount):
            # Extract member data from form
            member_name = form_data.get(f'member_{i}_name')
            member_github = form_data.get(f'member_{i}_githubUsername', '')
            member_resume = form_data.get(f'member_{i}_resumeFile')

            if not member_name:
                continue

            # Find or create member
            members = db["members"]
            m = find_by_name(members, member_name)
            if not m:
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
                if member_github:
                    m["github_url"] = f"https://github.com/{member_github}"

            # Save resume file if provided
            resume_path = None
            if member_resume and hasattr(member_resume, 'read'):
                ext = os.path.splitext(getattr(member_resume, 'filename', 'resume.pdf'))[1] or ".pdf"
                dest = os.path.join(UPLOAD_DIR, f"{m['member_id']}{ext}")

                content = await member_resume.read()
                with open(dest, "wb") as f:
                    f.write(content)
                m["resume_path"] = dest
                resume_path = dest

            # Run skill extraction
            skill_results = run_skill_extraction(
                github_url=m.get("github_url"),
                resume_path=resume_path or m.get("resume_path")
            )

            # Merge + dedupe with existing data
            m["languages"] = norm_list((m.get("languages") or []) + (skill_results.get("languages") or []))
            m["skills"]     = norm_list((m.get("skills") or []) + (skill_results.get("skills") or []))
            m["keywords"]   = norm_list((m.get("keywords") or []) + (skill_results.get("keywords") or []))

            processed_members.append(m)

        # --- Role Matching Logic ---
        role_names = list(roles.keys())
        person_names = [p['name'] for p in processed_members]
        person_skills = [" ".join(p['skills'] + p['languages'] + p['keywords']) for p in processed_members]

        role_embeddings = np.vstack([get_embedding(text) for text in roles.values()])
        person_embeddings = np.vstack([get_embedding(text) for text in person_skills])

        sim_matrix = cosine_similarity(role_embeddings, person_embeddings)

        assignments = {}
        remaining_people = set(range(len(person_names)))

        for i, role in enumerate(role_names):
            sims = sim_matrix[i, :]
            best_idx = max(remaining_people, key=lambda j: sims[j]) if remaining_people else None
            if best_idx is not None:
                best_person = person_names[best_idx]
                assignments[role] = best_person
                remaining_people.remove(best_idx)

        # Save updated database
        save_db(db)

        return {
            "success": True,
            "data": {
                "specifications": specs,
                "processed_members": processed_members,
                "role_assignments": assignments,
                "similarity_matrix": sim_matrix.tolist()
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )