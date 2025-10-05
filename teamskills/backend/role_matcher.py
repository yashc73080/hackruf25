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

# ---------------------- Domain-aware adjustments ----------------------

# Default domain anchors describe common domains with rich seed phrases.
DEFAULT_DOMAIN_ANCHORS: dict[str, str] = {
    "frontend": (
        "frontend web development; UI; UX; React; Next.js; JavaScript; TypeScript; HTML; CSS; Tailwind; accessibility; design systems"
    ),
    "backend": (
        "backend server development; APIs; microservices; databases; PostgreSQL; MySQL; Redis; Node.js; Python; Java; Go; REST; GraphQL; scalability; reliability"
    ),
    "data-ml": (
        "data science; machine learning; deep learning; statistics; pandas; numpy; scikit-learn; TensorFlow; PyTorch; data pipelines; feature engineering; MLOps"
    ),
    "devops": (
        "DevOps; CI/CD; Docker; Kubernetes; Terraform; Infrastructure as Code; AWS; Azure; GCP; observability; logging; monitoring; SRE"
    ),
    "mobile": (
        "mobile development; iOS; Android; Swift; Kotlin; React Native; Flutter; mobile UI; app store; device APIs"
    ),
    "security": (
        "cybersecurity; application security; encryption; IAM; vulnerability; pentesting; threat modeling; OWASP; zero trust"
    ),
    "product-design": (
        "product management; product discovery; UX research; UI design; interaction design; prototyping; Figma; user testing"
    ),
    "finance": (
        "finance; accounting; financial markets; trading; investment banking; quant; derivatives; portfolio; risk management; fintech; payments"
    ),
    "healthcare": (
        "healthcare; medical; clinical; EHR; patient care; HIPAA; biomed; pharma; diagnostics; public health"
    ),
    "education": (
        "education; edtech; pedagogy; teaching; curriculum; learning science; assessment; LMS"
    ),
}

def _softmax(x: np.ndarray, temperature: float = 1.0, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax with temperature.
    If temperature < 1, sharpening; > 1, smoothing.
    """
    if temperature <= 0:
        temperature = 1.0
    x_scaled = x / float(temperature)
    x_max = np.max(x_scaled, axis=axis, keepdims=True)
    e_x = np.exp(x_scaled - x_max)
    sum_e = np.sum(e_x, axis=axis, keepdims=True)
    return e_x / np.clip(sum_e, 1e-9, None)

def _build_domain_anchor_embeddings(embed_fn, anchors: dict[str, str] | None = None):
    """Create embeddings for domain anchors. Returns (names, embeddings[np.ndarray])."""
    anchors = anchors or DEFAULT_DOMAIN_ANCHORS
    names = list(anchors.keys())
    texts = [anchors[n] for n in names]
    embs = np.vstack([embed_fn(t) for t in texts])
    return names, embs

def _domain_alignment_matrix(
    role_embs: np.ndarray,
    member_embs: np.ndarray,
    anchor_names: list[str],
    anchor_embs: np.ndarray,
    temperature: float = 0.7,
    method: str = "dot",
) -> tuple[np.ndarray, dict]:
    """Compute a role×member matrix of domain alignment based on similarities to anchor domains.
    - role_embs: (R, d)
    - member_embs: (M, d)
    - anchor_embs: (D, d)
    Returns (alignment[R,M] in [0,1], debug_info)
    """
    # Similarity of roles/members to each anchor
    role_vs_anchor = cosine_similarity(role_embs, anchor_embs)  # (R, D)
    member_vs_anchor = cosine_similarity(member_embs, anchor_embs)  # (M, D)

    # Convert to distributions over domains for each role/member (sharpen a bit)
    role_dist = _softmax(role_vs_anchor, temperature=temperature, axis=1)  # (R, D)
    member_dist = _softmax(member_vs_anchor, temperature=temperature, axis=1)  # (M, D)

    # Compute alignment scores
    if method == "cosine":
        # Normalize distributions to unit length then cosine between them
        def _norm(x):
            n = np.linalg.norm(x, axis=1, keepdims=True)
            return x / np.clip(n, 1e-9, None)
        r_n = _norm(role_dist)
        m_n = _norm(member_dist)
        align = r_n @ m_n.T  # (R, M) in [0,1]
    else:
        # Default: dot-product of probability vectors (expected overlap), in [0,1]
        align = role_dist @ member_dist.T

    # Prepare compact debug info
    debug = {
        "anchors": anchor_names,
        "roles": [
            {
                "top": anchor_names[int(np.argmax(role_vs_anchor[i]))],
                "scores": role_vs_anchor[i].tolist(),
            }
            for i in range(role_vs_anchor.shape[0])
        ],
        "members": [
            {
                "name_index": j,
                "top": anchor_names[int(np.argmax(member_vs_anchor[j]))],
                "scores": member_vs_anchor[j].tolist(),
            }
            for j in range(member_vs_anchor.shape[0])
        ],
    }
    return align, debug

def _normalize_roles(roles_input):
    """Normalize roles to a mapping of name->text restricted to core_skills only.
    Returns (roles_map, roles_debug) where roles_debug lists core_skills used and the final text.
    """
    out = {}
    debug = []
    if isinstance(roles_input, dict):
        for k, v in (roles_input or {}).items():
            name = str(k)
            core = []
            if isinstance(v, dict):
                core = v.get("core_skills") or v.get("skills") or []
            text = ("Core skills: " + ", ".join(core) + ".") if core else ""
            out[name] = text
            debug.append({"role": name, "core_skills": list(core), "text": text})
        return out, debug
    for i, r in enumerate(roles_input or []):
        if isinstance(r, dict):
            name = r.get("title") or r.get("name") or f"Role {i+1}"
            core = r.get("core_skills") or r.get("skills") or []
            text = ("Core skills: " + ", ".join(core) + ".") if core else ""
            out[str(name)] = text
            debug.append({"role": str(name), "core_skills": list(core), "text": text})
        else:
            role_name = f"Role {i+1}"
            out[role_name] = ""
            debug.append({"role": role_name, "core_skills": [], "text": ""})
    return out, debug

def _normalize_members(members_input, top_k: int | None = None, weights: dict | None = None):
    """Accepts members as list[dict] with name and arrays (skills, languages, keywords).
    Returns (names, texts, debug_members). If top_k is set, only the first top_k items in each array are used (assuming strongest-first ordering).
    Weights can emphasize categories, e.g., {"skills": 2.0, "languages": 2.0, "keywords": 1.0}. debug_members captures exact arrays and text used.
    """
    names, texts = [], []
    debug_members = []
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
        selected_top_k = None
        if isinstance(top_k, int) and top_k > 0:
            skills = list(skills)[:top_k]
            languages = list(languages)[:top_k]
            keywords = list(keywords)[:top_k]
            selected_top_k = top_k
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

        # Thorough logging of what is being sent for embedding
        try:
            k_label = selected_top_k if selected_top_k is not None else "ALL"
            print(f"[role_matcher] Member '{name}' embedding inputs (top_k={k_label}):")
            print(f"  skills   ({len(skills)}): {skills}")
            print(f"  languages({len(languages)}): {languages}")
            print(f"  keywords ({len(keywords)}): {keywords}")
            preview = (text[:300] + '...') if len(text) > 300 else text
            print(f"  text_for_embedding[{len(text)}]: {preview}")
        except Exception:
            pass
        names.append(str(name))
        texts.append(text)
        # Collect debug info for frontend logging
        debug_members.append({
            "name": str(name),
            "top_k_used": selected_top_k,
            "skills": list(skills),
            "languages": list(languages),
            "keywords": list(keywords),
            "text": text,
        })
    return names, texts, debug_members

"""
Softmax removed: we rely on raw cosine and a normalized share percent only.
"""

def match_roles(
    roles,
    members,
    embed_fn=None,
    top_k: int | None = None,
    weights: dict | None = None,
    domain_boost: dict | None = None,
    softmax_temperature: float | None = 0.6,
):
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

    roles_map, roles_debug = _normalize_roles(roles)
    role_names = list(roles_map.keys())
    role_texts = list(roles_map.values())

    member_names, member_texts, member_debug = _normalize_members(members, top_k=top_k, weights=weights)

    if not role_names or not member_names:
        return {"assignments": {}, "similarity_matrix": [], "reports": []}

    role_embeddings = np.vstack([embed_fn(t) for t in role_texts])
    member_embeddings = np.vstack([embed_fn(t) for t in member_texts])

    # Base cosine similarity
    sim_matrix = cosine_similarity(role_embeddings, member_embeddings)

    # Optional: amplify domain (mis)match using anchor-based alignment
    domain_debug = None
    cfg = domain_boost or {}
    enabled = cfg.get("enabled", True)
    strength = float(cfg.get("strength", 0.35))  # 0..1, where 0=no effect
    if enabled and strength > 0:
        anchors = cfg.get("anchors")
        temperature = float(cfg.get("temperature", 0.7))
        method = str(cfg.get("method", "dot"))  # 'dot' or 'cosine'
        anchor_names, anchor_embs = _build_domain_anchor_embeddings(embed_fn, anchors=anchors)
        align_matrix, align_debug = _domain_alignment_matrix(
            role_embeddings, member_embeddings, anchor_names, anchor_embs, temperature=temperature, method=method
        )
        # Scale similarities: boost when aligned, reduce when misaligned
        # Map alignment [0,1] -> scale [1-strength, 1+strength]
        scale = 1.0 + strength * (2.0 * align_matrix - 1.0)
        sim_matrix = sim_matrix * scale
        domain_debug = {
            "strength": strength,
            "temperature": temperature,
            "method": method,
            "alignment_preview": {
                "min": float(np.min(align_matrix)),
                "max": float(np.max(align_matrix)),
                "mean": float(np.mean(align_matrix)),
            },
            **align_debug,
        }

    assignments = {}
    reports = []
    remaining = set(range(len(member_names)))
    for i, role in enumerate(role_names):
        sims = sim_matrix[i, :]
        # Compute softmax-enhanced scores for display (amplify differences)
        soft_scores = _softmax(np.array(sims, dtype=np.float64).reshape(1, -1), temperature=(softmax_temperature or 1.0), axis=1)[0]
        best_idx = max(remaining, key=lambda j: sims[j]) if remaining else None
        if best_idx is not None:
            assignments[role] = member_names[best_idx]
            remaining.remove(best_idx)
        # Build per-role report regardless
        # Keep raw cosine similarities and softmax-enhanced scores for transparency
        ranked = sorted(
            (
                {
                    "member": member_names[j],
                    "score": float(sims[j]),
                    "soft_score": float(soft_scores[j]),
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
                f"Role '{role}': cosine similarity computed and softmax-enhanced for display. "
                f"Top: {top['member']} (cos={top['score']:.4f}, soft={top.get('soft_score', 0.0):.4f})."
            )
        else:
            log = f"Role '{role}': no candidates available."
        reports.append({
            "role": role,
            "candidates": ranked,
            "winner": winner_name,
            "log": log,
        })

    return {
        "assignments": assignments,
        "similarity_matrix": sim_matrix.tolist(),
        "reports": reports,
        "debug": {
            "top_k": top_k,
            "members": member_debug,
            "roles": roles_debug,
            "domain": domain_debug,
            "softmax_temperature": softmax_temperature,
        },
    }

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