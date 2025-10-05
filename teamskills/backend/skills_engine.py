import math
from typing import List, Dict, Tuple

# Very small deterministic skills extractor + simple embedding (bag-of-words)
# This is a lightweight, hackathon-friendly module that turns a list of keywords
# into a sparse vector and computes cosine similarity.

# A tiny curated keyword list for demonstration. Extend as needed.
KEYWORDS = [
    "python",
    "javascript",
    "react",
    "nextjs",
    "fastapi",
    "flask",
    "docker",
    "ml",
    "pytorch",
    "tensorflow",
    "sql",
    "postgres",
    "mongodb",
    "html",
    "css",
    "typescript",
]

KEY_INDEX = {k: i for i, k in enumerate(KEYWORDS)}


def extract_keywords_from_text(text: str) -> List[str]:
    """Very simple keyword extractor: lowercase, split, and match KEYWORDS.
    Returns list of matched keywords (no weights)."""
    if not text:
        return []
    s = text.lower()
    found = set()
    for k in KEYWORDS:
        if k in s:
            found.add(k)
    return sorted(found)


def vectorize_keywords(keywords: List[str]) -> List[float]:
    vec = [0.0] * len(KEYWORDS)
    for k in keywords:
        idx = KEY_INDEX.get(k)
        if idx is not None:
            vec[idx] = 1.0
    return vec


def dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(a: List[float]) -> float:
    return math.sqrt(dot(a, a))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    na = norm(a)
    nb = norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)


def profile_to_vector(profile: Dict) -> List[float]:
    """Given a scraped profile dict (as returned by summarize_user or similar),
    combine README snippets and language names to a keyword list and vectorize.
    Expected profile keys: 'repos' (list of repo entries), 'overall_language_percentages'."""
    texts = []
    # add readme snippets
    for r in profile.get("repos", []):
        rd = r.get("readme_snippet")
        if rd:
            texts.append(rd)
    # add language names
    langs = profile.get("overall_language_percentages", [])
    for l in langs:
        texts.append(l.get("name", ""))
    big = "\n\n".join(texts)
    kws = extract_keywords_from_text(big)
    vec = vectorize_keywords(kws)
    return vec


def match_project(requirements_text: str, profiles: Dict[str, Dict]) -> List[Tuple[str, float, List[str]]]:
    """Given a project requirements string and a dict of profiles keyed by username,
    return a ranked list of (username, score, matched_keywords).
    """
    req_kws = extract_keywords_from_text(requirements_text)
    req_vec = vectorize_keywords(req_kws)
    out = []
    for user, p in profiles.items():
        v = profile_to_vector(p)
        score = cosine_similarity(req_vec, v)
        # matched keywords intersection
        matched = [k for k in req_kws if k in extract_keywords_from_text("\n".join([
            (r.get("readme_snippet") or "") + " " + " ".join([l.get("name","") for l in p.get("overall_language_percentages", [])])
            for r in p.get("repos", [])
        ]))]
        out.append((user, score, matched))
    out.sort(key=lambda x: x[1], reverse=True)
    return out
