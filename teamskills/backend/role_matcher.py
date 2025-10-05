#!/usr/bin/env python3
"""
role_matcher.py
Semantic role→person assignment using Gemini embeddings and cosine similarity.
Exposes a reusable function `match_roles(roles, members, embed_fn=None)` compatible with the app's JSON.
"""

import os
import numpy as np
import json  # Add this
import traceback  # Add this if you want error handling
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
import google.generativeai as genai

# Load env from repo root if available (for GEMINI_API_KEY)
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.local"))
load_dotenv(dotenv_path)

def _configure_genai():
    """Configure Gemini API - simplified version like your old code"""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY not found. Checked path: {dotenv_path}")
    
    print(f"🔑 Found API key: {api_key[:10]}...")  # Debug output
    genai.configure(api_key=api_key)
    print("✅ Gemini configured successfully")  # Debug output

def _default_get_embedding(text: str) -> np.ndarray:
    """Embedding via Gemini models/embedding-001 - simplified like your old code"""
    response = genai.embed_content(
        model="models/embedding-001",
        content=text or "",
        task_type="semantic_similarity",
    )
    return np.array(response["embedding"], dtype=np.float32)

def _normalize_roles(roles_input):
    """Accepts roles as list[dict] with title/description/fields or dict[str,str]; returns dict[name->text]."""
    if isinstance(roles_input, dict):
        return {str(k): str(v) for k, v in roles_input.items()}
    out = {}
    for i, r in enumerate(roles_input or []):
        if isinstance(r, dict):
            name = r.get("title") or r.get("name") or f"Role {i+1}"
            # Prefer concatenation of meaningful fields
            parts = []
            purp = r.get("purpose") or r.get("description") or ""
            if purp:
                parts.append(f"Purpose: {purp}.")
            resp = r.get("responsibilities") or []
            if resp:
                parts.append("Responsibilities: " + ", ".join(resp) + ".")
            core = r.get("core_skills") or r.get("skills") or []
            if core:
                parts.append("Core skills: " + ", ".join(core) + ".")
            nice = r.get("nice_to_have") or []
            if nice:
                parts.append("Nice to have: " + ", ".join(nice) + ".")
            text = " ".join([p for p in parts if p])
            out[str(name)] = text.strip() or name
        else:
            out[f"Role {i+1}"] = str(r)
    return out

def _normalize_members(members_input, top_k: int | None = None, weights: dict | None = None):
    """Accepts members as list[dict] with name and arrays (skills, languages, keywords).
    Returns (names, texts). If top_k is set, only the first top_k items in each array are used (assuming strongest-first ordering).
    Weights can emphasize categories, e.g., {"skills": 2.0, "languages": 2.0, "keywords": 1.0}.
    """
    names, texts = [], []
    weights = weights or {"skills": 2.0, "languages": 2.0, "keywords": 1.0}
    for m in members_input or []:
        if not isinstance(m, dict):
            continue
        name = m.get("name") or m.get("id") or "Member"
        # Support various keys
        skills = m.get("skills") or []
        languages = m.get("languages") or m.get("programming_languages") or []
        keywords = m.get("keywords") or m.get("notable_keywords") or []
        # Take strongest-first subset if requested
        if isinstance(top_k, int) and top_k > 0:
            skills = list(skills)[:top_k]
            languages = list(languages)[:top_k]
            keywords = list(keywords)[:top_k]
        # Flatten to a single string for embedding; add light templating for context
        def _flatten(seq):
            bag = []
            if isinstance(seq, dict):
                for v in seq.values():
                    bag.extend(v if isinstance(v, list) else [v])
            else:
                bag.extend(seq if isinstance(seq, list) else [seq])
            return [str(t) for t in bag if t]

        skills_txt = ", ".join(_flatten(skills))
        langs_txt = ", ".join(_flatten(languages))
        keys_txt = ", ".join(_flatten(keywords))
        parts = []
        # Apply category weighting by repeating emphasized phrases
        if skills_txt:
            skills_line = f"Top skills: {skills_txt}."
            parts.extend([skills_line] * max(1, int(round(weights.get("skills", 1.0)))))
        if langs_txt:
            langs_line = f"Programming languages: {langs_txt}."
            parts.extend([langs_line] * max(1, int(round(weights.get("languages", 1.0)))))
        if keys_txt:
            keys_line = f"Keywords: {keys_txt}."
            parts.extend([keys_line] * max(1, int(round(weights.get("keywords", 1.0)))))
        text = " ".join(parts).strip()
        names.append(str(name))
        texts.append(text)
    return names, texts

def _softmax(x: np.ndarray, temperature: float = 0.6) -> np.ndarray:
    # Numerically stable softmax with temperature
    x_scaled = x / max(temperature, 1e-6)
    x_shift = x_scaled - np.max(x_scaled)
    e = np.exp(x_shift)
    s = e.sum() or 1.0
    return e / s

def match_roles(roles, members, embed_fn=None, top_k: int | None = None, weights: dict | None = None):
    """
    Compute role→member assignment using embeddings and cosine similarity.

    roles: dict[str,str] or list[dict{title,purpose,responsibilities,core_skills,nice_to_have,...}]
    members: list[dict{name, skills, languages, keywords}]
    embed_fn: optional callable(text)->np.ndarray, defaults to Gemini embedding

    Returns: {
        "assignments": {role_name: member_name},
        "similarity_matrix": [[...]],
        "reports": [
            {
                "role": role_name,
                "candidates": [ {"member": name, "score": float, "percent": float} ... ],
                "winner": member_name,
                "log": str
            },
            ...
        ]
    }
    """
    if embed_fn is None:
        _configure_genai()
        embed_fn = _default_get_embedding

    roles_map = _normalize_roles(roles)
    role_names = list(roles_map.keys())
    role_texts = list(roles_map.values())

    member_names, member_texts = _normalize_members(members, top_k=top_k, weights=weights)

    if not role_names or not member_names:
        return {"assignments": {}, "similarity_matrix": [], "reports": []}

    role_embeddings = np.vstack([embed_fn(t) for t in role_texts])
    member_embeddings = np.vstack([embed_fn(t) for t in member_texts])

    sim_matrix = cosine_similarity(role_embeddings, member_embeddings)

    assignments = {}
    reports = []
    remaining = set(range(len(member_names)))
    for i, role in enumerate(role_names):
        sims = sim_matrix[i, :]
        best_idx = max(remaining, key=lambda j: sims[j]) if remaining else None
        if best_idx is not None:
            assignments[role] = member_names[best_idx]
            remaining.remove(best_idx)
        # Build per-role report regardless
        # Keep raw cosine similarities for transparency
        # Derive two normalized views:
        # 1) shifted-percent: share-of-positive (legacy)
        shifted = (sims + 1.0) / 2.0
        total = float(shifted.sum()) or 1.0
        percents = shifted / total
        # 2) softmax-percent with temperature for sharper separation
        softmax_p = _softmax(sims, temperature=0.6)
        ranked = sorted(
            (
                {
                    "member": member_names[j],
                    "score": float(sims[j]),
                    "percent": float(percents[j]),
                    "softmax_percent": float(softmax_p[j]),
                }
                for j in range(len(member_names))
            ),
            key=lambda x: x["score"],
            reverse=True,
        )
        winner_name = assignments.get(role) if role in assignments else (ranked[0]["member"] if ranked else None)
        if ranked:
            top = ranked[0]
            log = (
                f"Role '{role}': cosine similarity computed vs each member embedding. "
                f"Top: {top['member']} (cos={top['score']:.4f}, softmax={(top['softmax_percent']*100):.1f}%)."
            )
        else:
            log = f"Role '{role}': no candidates available."
        reports.append({
            "role": role,
            "candidates": ranked,
            "winner": winner_name,
            "log": log,
        })

    return {"assignments": assignments, "similarity_matrix": sim_matrix.tolist(), "reports": reports}

__all__ = ["match_roles"]

if __name__ == "__main__":
    # Quick test
    test_roles = {"frontend": "React JavaScript UI development", "backend": "Python API database"}
    test_members = [
        {"name": "Alice", "skills": ["React", "JavaScript"], "languages": ["JavaScript"], "keywords": ["frontend"]},
        {"name": "Bob", "skills": ["Python", "Django"], "languages": ["Python"], "keywords": ["backend", "API"]}
    ]
    
    try:
        result = match_roles(test_roles, test_members)
        print("✅ Test successful!")
        print(f"Assignments: {result['assignments']}")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()