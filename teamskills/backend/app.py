import os, sys, json, uuid, re, tempfile, subprocess
from typing import List, Optional
import traceback

from fastapi import FastAPI, UploadFile, Form, File, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Body
    
# --- Imports for Role Matching ---
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

# ---------------- import skill extractor ----------------
try:
    # Try absolute import first
    from skill_extractor import analyze_profile
except ImportError:
    try:
        # Try relative import if running as part of a package
        from .skill_extractor import analyze_profile
    except ImportError as e:
        print(f"Warning: Could not import skill_extractor: {e}")
        analyze_profile = None

# Specifications & Roles extraction
try:
    # Try absolute import first
    from planning_extractor import extract_specifications_from_chat, extract_roles_for_project
except ImportError:
    try:
        # Try relative import if running as part of a package
        from .planning_extractor import extract_specifications_from_chat, extract_roles_for_project
    except ImportError as e:
        print(f"Warning: Could not import planning_extractor: {e}")
        extract_specifications_from_chat = None
        extract_roles_for_project = None

# --- Load environment variables and configure Gemini ---
load_dotenv()
# Also try loading from parent directory
parent_dir = os.path.dirname(os.path.dirname(__file__))
env_local_path = os.path.join(parent_dir, '.env.local')
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)

import google.generativeai as genai

# Role matcher import
try:
    # Try absolute import first
    from role_matcher import match_roles
except ImportError:
    try:
        # Try relative import if running as part of a package
        from .role_matcher import match_roles
    except ImportError as e:
        print(f"Warning: Could not import role_matcher: {e}")
        match_roles = None

# --- Configure Gemini client ---
# Configure Gemini client safely
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    # Handle the case where the API key is not found
    print("GEMINI_API_KEY not found.")
    genai_configured = False
else:
    try:
        configure_fn = getattr(genai, "configure", None)
        if callable(configure_fn):
            configure_fn(api_key=api_key)
            genai_configured = True
        else:
            print("google.generativeai.configure not available")
            genai_configured = False
    except Exception as _e:
        print(f"Failed to configure Gemini: {_e}")
        genai_configured = False


# ---------------- paths & storage ----------------
DB_PATH = "team_members.json"
UPLOAD_DIR = "resumes"

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

# Safely coerce form values into strings
def coerce_text(v) -> str:
    try:
        if isinstance(v, UploadFile):
            return (v.filename or "")
        if isinstance(v, (bytes, bytearray)):
            try:
                return v.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(v or "")
    except Exception:
        return ""

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
    embed_content = getattr(genai, "embed_content", None)
    if not callable(embed_content):
        raise RuntimeError("google.generativeai.embed_content not available")
    response = embed_content(
        model="models/embedding-001",
        content=text,
        task_type="semantic_similarity"
    )
    # Support dict-like or attribute-based responses
    embedding = None
    if isinstance(response, dict):
        embedding = response.get("embedding")
    else:
        embedding = getattr(response, "embedding", None)
    if embedding is None:
        raise RuntimeError("Embedding not present in Gemini response")
    return np.array(embedding, dtype=np.float32)

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
app.mount("/resumes", StaticFiles(directory=UPLOAD_DIR, check_dir=False), name="resumes")

@app.post("/api/extract-specifications")
async def api_extract_specifications(payload: dict = Body(...)):
    """
    Generate a detailed project idea/specification from full chat context.
    Expects JSON: { messages: [{ role, content }, ...] }
    Returns: { success, data }
    """
    try:
        if not extract_specifications_from_chat:
            raise RuntimeError("planning_extractor not available")
        messages = payload.get("messages") or []
        data = extract_specifications_from_chat(messages)
        return {"success": True, "data": data}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/match-roles")
async def api_match_roles(payload: dict = Body(...)):
    """
    Match roles to members using embeddings and cosine similarity.
    Expects JSON: { roles: (dict or list), members: [ { name, skills, languages, keywords } ] }
    Returns: { success, data: { assignments, similarity_matrix } }
    """
    try:
        roles_in = payload.get("roles") or []
        members_in = payload.get("members") or payload.get("processed_members") or []
        top_k = payload.get("topK") or payload.get("top_k")
        try:
            top_k = int(top_k) if top_k is not None else None
        except Exception:
            top_k = None
        result = match_roles(roles_in, members_in, top_k=top_k)
        return {"success": True, "data": result}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/extract-roles")
async def api_extract_roles(payload: dict = Body(...)):
    """
    Derive exactly N complementary roles from the project idea.
    Expects JSON: { specifications: <object|string>, memberCount: number }
    Returns: { success, data: { roles: [...] } }
    """
    try:
        if not extract_roles_for_project:
            raise RuntimeError("planning_extractor not available")
        specs = payload.get("specifications")
        member_count = int(payload.get("memberCount") or payload.get("teamMembersCount") or 0)
        idea_text = json.dumps(specs, indent=2, ensure_ascii=False) if isinstance(specs, (dict, list)) else (specs or "")
        roles = extract_roles_for_project(idea_text, member_count)
        return {"success": True, "data": {"roles": roles}}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
@app.post("/api/extract-skills")
async def extract_skills(payload: dict = Body(...)):
    """
    Minimal extraction endpoint.
    Expects JSON: { specifications, teamMembersCount, members: [{ name, githubUsername, resumePath }] }
    Returns extracted skills per member and combined role matching (optional).
    """
    try:
        members_in = payload.get("members", []) or []
        processed_members = []

        for m in members_in:
            name = (m.get("name") or "").strip()
            gh = (m.get("githubUsername") or "").strip()
            resume_path = m.get("resumePath") or None
            github_url = f"https://github.com/{gh}" if gh else None

            skills = run_skill_extraction(github_url=github_url, resume_path=resume_path)
            processed_members.append({
                "name": name,
                "github_username": gh,
                "resume_path": resume_path,
                **skills,
            })

        # Just return the skills now; role matching can be added later if needed
        return { "success": True, "data": { "processed_members": processed_members } }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({ "success": False, "error": str(e) }, status_code=500)

@app.post("/api/process-team-data")
async def process_team_data(
    request: Request,
    specifications: str = Form(...),
    teamMembersCount: int = Form(...),
):
    """
    Process team data from TeamInputForm.jsx
    Expects: specifications, teamMembersCount, and member_X_* fields
    """
    try:
        specs = json.loads(specifications)
        roles = {spec.get("title", f"Role {i+1}"): spec.get("description", "") for i, spec in enumerate(specs)}
    except (json.JSONDecodeError, AttributeError, TypeError):
        specs = []
        roles = {"Default Role": "A generalist role for this project"}


    try:
        # Extract team members from form data
        form = await request.form()
        processed_members = []
        db = load_db()

        for i in range(teamMembersCount):
            # Extract member data from form
            raw_name = form.get(f'member_{i}_name')
            raw_github = form.get(f'member_{i}_githubUsername')
            member_resume = form.get(f'member_{i}_resumeFile')

            # Coerce to strings safely (guard against UploadFile or None)
            member_name = coerce_text(raw_name).strip()
            member_github = coerce_text(raw_github).strip()

            if not member_name:
                continue

            # Find or create member
            members = db["members"]
            m = find_by_name(members, member_name)
            if not m:
                m = {
                    "member_id": str(uuid.uuid4()),
                    "name": member_name,
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

            # Save resume file if provided (UploadFile via Starlette)
            resume_path = None
            try:
                if isinstance(member_resume, UploadFile):
                    if not os.path.isdir(UPLOAD_DIR):
                        raise RuntimeError(
                            f"Upload directory '{UPLOAD_DIR}' not found. Ensure it's mounted and accessible."
                        )
                    ext = os.path.splitext(getattr(member_resume, 'filename', 'resume.pdf'))[1] or ".pdf"
                    dest = os.path.join(UPLOAD_DIR, f"{m['member_id']}{ext}")
                    content = await member_resume.read()
                    with open(dest, "wb") as f:
                        f.write(content)
                    filename = os.path.basename(dest)
                    m["resume_path"] = dest
                    m["resume_filename"] = filename
                    m["resume_public_path"] = f"/resumes/{filename}"
                    # Absolute URL for convenience in the frontend
                    try:
                        base = str(request.base_url)  # e.g., http://127.0.0.1:8000/
                        if not base.endswith('/'):
                            base = base + '/'
                        m["resume_url"] = base + f"resumes/{filename}"
                    except Exception:
                        m["resume_url"] = f"/resumes/{filename}"
                    resume_path = dest
                    print(f"✅ Saved resume for {member_name}: {dest} -> mounted at {m['resume_public_path']}")
            except Exception as up_err:
                print(f"Warning: failed to save resume for {member_name}: {up_err}")

            # Preserve provided github username explicitly
            m["github_username"] = member_github

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

        assignments = {}
        if genai_configured and role_names and person_names:
            try:
                role_embeddings = np.vstack([get_embedding(text) for text in roles.values()])
                person_embeddings = np.vstack([get_embedding(text) for text in person_skills])

                sim_matrix = cosine_similarity(role_embeddings, person_embeddings)

                remaining_people = set(range(len(person_names)))
                for i, role in enumerate(role_names):
                    sims = sim_matrix[i, :]
                    best_idx = max(remaining_people, key=lambda j: sims[j]) if remaining_people else None
                    if best_idx is not None:
                        best_person = person_names[best_idx]
                        assignments[role] = best_person
                        remaining_people.remove(best_idx)
                sim_matrix_out = sim_matrix.tolist()
            except Exception as emb_err:
                print(f"Embedding/Similarity failed, skipping role matching: {emb_err}")
                sim_matrix_out = []
        else:
            # Skip similarity when embeddings unavailable
            sim_matrix_out = []

        # Save updated database
        save_db(db)

        return {
            "success": True,
            "data": {
                "specifications": specs,
                "processed_members": processed_members,
                "role_assignments": assignments,
                "similarity_matrix": sim_matrix_out
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )