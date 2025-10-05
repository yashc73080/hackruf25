#!/usr/bin/env python3
"""gemini_helper.py

Simple Gemini (Google generative API) helper to extract normalized skills from text.

Behavior:
- Uses environment variable GEMINI_API_KEY (or GOOGLE_API_KEY) via google.generativeai if available.
- Provides a cache on disk under repo-root .cache/gemini to avoid repeated calls.
- Returns a dict with tokens_normalized and raw response.

Dependencies (optional):
    pip install google-generativeai
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE_DIR = os.path.join(repo_root, ".cache", "gemini")
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_RETRIES = 3
RETRY_BACKOFF = 1.5

_CLIENT_AVAILABLE = False
genai: Any = None
try:
    import google.generativeai as genai_lib  # type: ignore
    genai = genai_lib
    _CLIENT_AVAILABLE = True
except Exception:
    genai = None
    _CLIENT_AVAILABLE = False


def _cache_path(key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")


def _read_cache(key: str) -> Optional[Dict]:
    p = _cache_path(key)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _write_cache(key: str, data: Dict) -> None:
    p = _cache_path(key)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def normalize_token(tok: str) -> str:
    t = tok.lower().strip()
    # simple normalization rules; extend later
    t = t.replace("react.js", "react").replace("reactjs", "react")
    t = t.replace("node.js", "node").replace("nodejs", "node")
    t = t.replace("postgresql", "postgres").replace("postgresql", "postgres")
    t = t.replace("c#", "csharp")
    t = t.strip(". ,;:\n\t")
    return t


def _build_prompt(text: str, source: str, domain_priority: str = "cs") -> str:
    # Keep prompts concise; request JSON-only output. domain_priority hints the model
    domain_hint = {
        "cs": "Prioritize computer-science/software engineering skills: programming languages, frameworks, libraries, tools, devops, cloud, databases, and ML infra.",
        "medical": "Prioritize clinical, medical, and healthcare skills, devices, and terminology, but also include software or data skills if present.",
        "finance": "Prioritize finance, trading, banking, and fintech skills, plus relevant software and analytics tools.",
    }.get(domain_priority.lower(), f"Prioritize {domain_priority} domain skills but include CS/software skills if present.")

    return (
        "You are a JSON-only extractor.\n"
        "%s\n"
        "Given the following %s text, extract a deduplicated list of technical skills, libraries, frameworks, tools, and services.\n"
        "Return ONLY valid JSON with fields: tokens_normalized (array of lowercase tokens). Optionally include a 'categories' map per token.\n"
        "Example output: {\"tokens_normalized\": [\"python\", \"fastapi\", \"docker\"]}\n"
        "Now analyze the text and output JSON.\n\nText:\n\n%s"
    ) % (domain_hint, source, text[:30000])


def extract_skills_from_text(text: str, source: str = "resume", domain_priority: str = "cs", retries: int = DEFAULT_RETRIES) -> Dict:
    """Call Gemini (Generative AI) to extract normalized skill tokens from text.

    Returns: {"tokens_normalized": [...], "raw": <raw model output str>}.
    """
    key = f"{domain_priority}:{source}:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

    cached = _read_cache(key)
    if cached:
        return cached

    prompt = _build_prompt(text, source, domain_priority=domain_priority)

    if not _CLIENT_AVAILABLE:
        # Best-effort fallback: naive heuristic split by non-alphanum; return no confidence
        toks = []
        words = set([w.lower().strip(".,;()[](){}:;\"'`)\n\t") for w in text.split() if len(w) > 2])
        for w in words:
            if any(ch.isdigit() for ch in w) and not w.isalpha():
                continue
            toks.append(normalize_token(w))

        toks = sorted(set([t for t in toks if len(t) > 1]))

        # If domain_priority is cs, promote common CS tokens if present
        if domain_priority.lower() == "cs":
            cs_boost = [
                "python", "java", "javascript", "typescript", "c++", "csharp", "go", "rust",
                "docker", "kubernetes", "aws", "gcp", "azure", "postgres", "mysql", "redis",
            ]
            toks = sorted(toks, key=lambda x: (0 if x in cs_boost else 1, x))

        out = {"tokens_normalized": toks, "raw": "_local_fallback_no_gemini_client", "domain_priority": domain_priority}
        _write_cache(key, out)
        return out

    # initialize client if needed (reads API key from env)
    # genai.configure(api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key is None:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set in environment")
    # configure client
    if genai is None:
        raise RuntimeError("generativeai client not available; install google-generativeai")
    genai.configure(api_key=api_key)

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            # Use the modern genai.chat.create; response shapes vary between lib versions
            resp = genai.chat.create(
                model="gemini-2.5-flash-lite",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_output_tokens=512,
            )

            # Pull assistant text from known response properties (best-effort)
            assistant_text = None
            try:
                # some versions provide 'content' or 'last' directly
                if hasattr(resp, "last") and isinstance(resp.last, str):
                    assistant_text = resp.last
                elif isinstance(resp, dict) and "candidates" in resp:
                    assistant_text = resp["candidates"][0]["content"]
                else:
                    # try to extract choices -> message -> content
                    assistant_text = str(resp)
            except Exception:
                assistant_text = str(resp)

            # find first { ... } block
            j = None
            try:
                import re

                m = re.search(r"\{[\s\S]*\}", assistant_text)
                if m:
                    j = json.loads(m.group(0))
            except Exception:
                j = None

            tokens = []
            if j and isinstance(j, dict) and "tokens_normalized" in j:
                tokens = [normalize_token(t) for t in j.get("tokens_normalized", [])]
                tokens = sorted(list(dict.fromkeys([t for t in tokens if t])))
            else:
                # fallback: attempt whitespace split heuristic
                tokens = []
                for w in set([w.lower().strip(".,;()[]") for w in text.split() if len(w) > 2]):
                    tokens.append(normalize_token(w))
                tokens = sorted(set([t for t in tokens if len(t) > 1]))

            # If domain priority is CS, try to surface common CS tokens first
            if domain_priority.lower() == "cs":
                cs_boost = set([
                    "python", "java", "javascript", "typescript", "c++", "csharp", "go", "rust",
                    "docker", "kubernetes", "aws", "gcp", "azure", "postgres", "mysql", "redis",
                ])
                tokens = sorted(tokens, key=lambda x: (0 if x in cs_boost else 1, x))

            out = {"tokens_normalized": tokens, "raw": assistant_text, "provenance": {"prompt_version": "v1"}, "domain_priority": domain_priority}
            _write_cache(key, out)
            return out
        except Exception as e:
            last_err = e
            backoff = RETRY_BACKOFF * (2 ** (attempt - 1))
            time.sleep(backoff)
            continue

    raise RuntimeError(f"Gemini extract failed after {retries} attempts: {last_err}")
