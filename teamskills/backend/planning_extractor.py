"""
planning_extractor.py

Generates a detailed project idea/specification from chat context and
derives distinct, complementary roles for a given team size using Gemini.
"""

import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

import google.generativeai as genai

# Load environment variables - check multiple locations
load_dotenv()
parent_dir = os.path.dirname(os.path.dirname(__file__))
env_local_path = os.path.join(parent_dir, '.env.local')
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GENAI_CONFIGURED = False
if GEMINI_API_KEY:
    try:
        _configure = getattr(genai, 'configure', None)
        if callable(_configure):
            _configure(api_key=GEMINI_API_KEY)
            GENAI_CONFIGURED = True
        else:
            print("google.generativeai.configure not available")
    except Exception as e:
        print(f"Warning: Failed to configure Gemini: {e}")


def _build_chat_context_text(messages: List[Dict[str, Any]]) -> str:
    """Flatten chat messages into a readable transcript string."""
    lines = []
    for m in messages or []:
        role = (m.get('role') or 'user').strip()
        content = (m.get('content') or '').strip()
        # Skip empty lines and our explicit confirmation phrase if present
        if not content:
            continue
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def extract_specifications_from_chat(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Produce a well-formed project idea/specification from the full chat context.
    If details are sparse, the model fleshes them out while adhering closely to
    the given context. Output is structured JSON.
    """
    if not GENAI_CONFIGURED:
        raise RuntimeError("Gemini API key not configured")

    transcript = _build_chat_context_text(messages)

    prompt = f"""
You are a senior product strategist. Given a chat transcript where a team discusses a project idea, synthesize a detailed, coherent project specification. Adhere closely to the context. If information is missing, responsibly flesh out details while staying consistent with the user's intent.

Return strictly JSON with the following keys:
- idea_title: string
- idea_summary: string (3-6 sentences)
- objectives: string[] (5-10 items)
- core_features: string[] (8-15 items)
- stretch_goals: string[] (3-8 items)
- constraints: string[] (assumptions, data/tech constraints)
- deliverables: string[] (milestones/artefacts)
- timeline_phases: string[] (phases like Research, MVP, Alpha, Beta)
- skills: object with keys:
  - technical: string[]
  - soft: string[]
  - domain: string[]
  - tools: string[]
  - other: string[]
- risks: string[]
- success_metrics: string[]

Chat transcript:\n{transcript}
"""

    Model = getattr(genai, 'GenerativeModel', None)
    if not callable(Model):
        raise RuntimeError('google.generativeai.GenerativeModel not available')
    model = Model('gemini-2.5-flash-lite')
    gen_fn = getattr(model, 'generate_content', None)
    if not callable(gen_fn):
        raise RuntimeError('generate_content not available on model')
    response = gen_fn(prompt)
    # Try best-effort extraction of text
    text = getattr(response, 'text', None)
    if not text:
        text = str(response)
    text = text.strip()

    # Unwrap code fences if present
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    try:
        data = json.loads(text)
    except Exception:
        # Fallback minimal structure
        data = {
            "idea_title": "Generated Project Idea",
            "idea_summary": text[:1000],
            "objectives": [],
            "core_features": [],
            "stretch_goals": [],
            "constraints": [],
            "deliverables": [],
            "timeline_phases": [],
            "skills": {"technical": [], "soft": [], "domain": [], "tools": [], "other": []},
            "risks": [],
            "success_metrics": [],
        }
    return data


def extract_roles_for_project(idea_text: str, member_count: int) -> List[Dict[str, Any]]:
    """
    Generate exactly `member_count` distinct, complementary roles aligned to the project idea.
    Each role must have: title, purpose, responsibilities (3-6), core_skills (8-15), nice_to_have (4-8), collaboration_notes.
    Returns a list of role dicts.
    """
    if not GENAI_CONFIGURED:
        raise RuntimeError("Gemini API key not configured")

    member_count = int(member_count or 0)
    if member_count <= 0:
        return []

    prompt = f"""
You are a technical program manager. Based on the following project idea, design exactly {member_count} distinct and complementary team roles that together cover the work needed. Roles must not overlap significantly.

Return strictly JSON like:
[
  {{
    "title": "...",
    "purpose": "...",
    "responsibilities": ["..."],
    "core_skills": ["..."],
    "nice_to_have": ["..."],
    "collaboration_notes": "..."
  }},
  ... (total {member_count})
]

Project idea/context:\n{idea_text}
"""

    Model = getattr(genai, 'GenerativeModel', None)
    if not callable(Model):
        raise RuntimeError('google.generativeai.GenerativeModel not available')
    model = Model('gemini-2.5-flash-lite')
    gen_fn = getattr(model, 'generate_content', None)
    if not callable(gen_fn):
        raise RuntimeError('generate_content not available on model')
    response = gen_fn(prompt)
    text = getattr(response, 'text', None)
    if not text:
        text = str(response)
    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    try:
        roles = json.loads(text)
        if not isinstance(roles, list):
            raise ValueError("Roles JSON is not a list")
        # Ensure exact count by truncating or padding (padding with minimal roles if needed)
        if len(roles) > member_count:
            roles = roles[:member_count]
        elif len(roles) < member_count:
            # pad with generic helper roles
            for i in range(member_count - len(roles)):
                roles.append({
                    "title": f"Contributor {len(roles)+1}",
                    "purpose": "Support cross-functional tasks across the project",
                    "responsibilities": ["Assist core streams", "QA and documentation", "Coordinate with team"],
                    "core_skills": ["communication", "organization", "adaptability"],
                    "nice_to_have": ["prior project experience"],
                    "collaboration_notes": "Pairs with each role as needed to fill gaps.",
                })
    except Exception:
        roles = []
    return roles
