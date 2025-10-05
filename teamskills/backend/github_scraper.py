import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

# ---------- Setup ----------
load_dotenv()
API = "https://api.github.com"
GRAPHQL_URL = f"{API}/graphql"

TOKEN = os.getenv("GITHUB_TOKEN")
REST_HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
GQL_HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

# Small on-disk cache for development to avoid excessive GitHub calls
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE_DIR = os.path.join(repo_root, ".cache", "github")
os.makedirs(CACHE_DIR, exist_ok=True)
TOP_N = int(os.getenv("TOP_N", "5"))
CACHE_TTL = int(os.getenv("GITHUB_CACHE_TTL", "3600"))


def _cache_get(key: str) -> Optional[dict]:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        if time.time() - mtime > CACHE_TTL:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_set(key: str, value: dict):
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f)
    except Exception:
        pass

# ---------- HTTP helpers ----------
def rest_get_json(url):
    r = requests.get(url, headers=REST_HEADERS if TOKEN else {})
    return r.json() if r.status_code == 200 else None

def graphql_post(query, variables=None):
    if not TOKEN:
        return None
    r = requests.post(GRAPHQL_URL, headers=GQL_HEADERS, json={"query": query, "variables": variables or {}})
    if r.status_code != 200:
        return None
    j = r.json()
    if "errors" in j:
        return None
    return j

# ---------- Authenticated user ----------
def get_authenticated_login():
    if not TOKEN:
        return None
    me = rest_get_json(f"{API}/user")
    return me.get("login") if me else None

# ---------- Data fetch ----------
def list_affiliated_repos_for_self():
    """
    For the authenticated user only:
    Include repos where you are owner, collaborator, or org member.
    """
    if not TOKEN:
        return []
    repos = []
    page = 1
    while True:
        url = f"{API}/user/repos?per_page=100&affiliation=owner,collaborator,organization_member&page={page}"
        data = rest_get_json(url) or []
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos

def list_owned_repos(user):
    url = f"{API}/users/{user}/repos?per_page=100&type=owner&sort=updated"
    return rest_get_json(url) or []

def list_contributed_repos_graphql(user, first=100):
    """
    All-time contributed repos via top-level GraphQL field (not time-limited).
    Public by default; include private if token has `repo` scope and user == token owner (or you have access).
    Paginates.
    """
    if not TOKEN:
        return []

    query = """
    query($login: String!, $first: Int!, $after: String) {
      user(login: $login) {
        repositoriesContributedTo(
          first: $first,
          after: $after,
          includeUserRepositories: true,
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY],
          orderBy: {field: PUSHED_AT, direction: DESC}
        ) {
          pageInfo { hasNextPage endCursor }
          nodes {
            nameWithOwner
            stargazerCount
            updatedAt
            isPrivate
          }
        }
      }
    }
    """

    vars = {"login": user, "first": 100, "after": None}
    out, seen = [], set()
    for _ in range(20):
        data = graphql_post(query, vars)
        if not data:
            break
        block = (data.get("data", {})
                    .get("user", {})
                    .get("repositoriesContributedTo", {}))
        nodes = block.get("nodes", []) or []
        for n in nodes:
            full = n.get("nameWithOwner", "")
            if "/" in full and full not in seen:
                seen.add(full)
                owner, name = full.split("/", 1)
                out.append({
                    "owner": owner,
                    "name": name,
                    "stargazers_count": n.get("stargazerCount", 0),
                    "updated_at": n.get("updatedAt"),
                    "is_private": n.get("isPrivate", False)
                })
        if not block.get("pageInfo", {}).get("hasNextPage"):
            break
        vars["after"] = block["pageInfo"]["endCursor"]
    return out


def get_repo_readme(owner: str, name: str) -> Optional[str]:
    """Fetch README via REST API and return a decoded snippet (~2000 chars) or None."""
    cache_key = f"readme_{owner}_{name}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached.get("readme")
    url = f"{API}/repos/{owner}/{name}/readme"
    r = requests.get(url, headers=REST_HEADERS if TOKEN else {})
    if r.status_code != 200:
        _cache_set(cache_key, {"readme": None})
        return None
    try:
        j = r.json()
        content = j.get("content")
        enc = j.get("encoding")
        if content and enc == "base64":
            raw = base64.b64decode(content).decode("utf-8", errors="replace")
            snippet = raw[:2000]
            _cache_set(cache_key, {"readme": snippet})
            return snippet
    except Exception:
        pass
    _cache_set(cache_key, {"readme": None})
    return None

def list_contributed_repos_events(user, max_repos=30, max_pages=3):
    """
    Fallback: recent public PushEvents (works without token).
    Returns [{owner, name}]
    """
    repos, seen = [], set()
    for page in range(1, max_pages + 1):
        url = f"{API}/users/{user}/events/public?per_page=100&page={page}"
        r = requests.get(url, headers=REST_HEADERS if TOKEN else {})
        if r.status_code != 200:
            break
        events = r.json() or []
        if not events:
            break
        for ev in events:
            if ev.get("type") == "PushEvent":
                full = ev.get("repo", {}).get("name")  # "owner/repo"
                if full and full not in seen and "/" in full:
                    seen.add(full)
                    owner, name = full.split("/", 1)
                    repos.append({"owner": owner, "name": name})
                    if len(repos) >= max_repos:
                        return repos
    return repos


def recent_pushes_30d(user, max_pages=5):
    """Count PushEvents by this user in last 30 days (public events)."""
    cache_key = f"pushes_{user}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached.get("count", 0)
    cutoff = time.time() - (30 * 24 * 3600)
    count = 0
    for page in range(1, max_pages + 1):
        url = f"{API}/users/{user}/events/public?per_page=100&page={page}"
        r = requests.get(url, headers=REST_HEADERS if TOKEN else {})
        if r.status_code != 200:
            break
        events = r.json() or []
        if not events:
            break
        for ev in events:
            if ev.get("type") != "PushEvent":
                continue
            created = ev.get("created_at")
            try:
                # Normalize ISO8601: handle fractional seconds and trailing 'Z'
                if not created:
                    raise ValueError("no timestamp")
                s = created
                # if ends with Z (UTC), replace with +00:00 for fromisoformat
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                # if fractional seconds exist, fromisoformat handles them
                dt = datetime.fromisoformat(s)
                t = dt.timestamp()
            except Exception:
                t = 0
            if t >= cutoff:
                count += 1
    _cache_set(cache_key, {"count": count})
    if count > 0:
        _cache_set(cache_key, {"count": count})
        return count

    # Fallback: count repos (owned + contributed) with updated_at within past 30 days
    # make cutoff a timezone-aware UTC datetime to compare against parsed ISO datetimes
    try:
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
    except Exception:
        # fallback to naive UTC if timezone attribute missing
        cutoff_dt = datetime.utcfromtimestamp(cutoff)
    recent_repos = 0
    try:
        owned = list_owned_repos(user) or []
        for r in owned:
            updated = r.get("pushed_at") or r.get("updated_at")
            if updated:
                s = updated
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(s)
                    # ensure dt is timezone-aware; treat naive as UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                try:
                    if dt >= cutoff_dt:
                        recent_repos += 1
                except Exception:
                    # If comparison fails for any reason, skip this repo
                    continue
        contributed = list_contributed_repos_graphql(user, first=100) or []
        for c in contributed:
            updated = c.get("updated_at")
            if not updated:
                m = get_repo_meta(c.get("owner"), c.get("name"))
                updated = m.get("updated_at") if m else None
            if updated:
                s = updated
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(s)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                try:
                    if dt >= cutoff_dt:
                        recent_repos += 1
                except Exception:
                    continue
    except Exception:
        recent_repos = 0

    _cache_set(cache_key, {"count": recent_repos})
    return recent_repos

    # fallback: if no events visible (often due to privacy/rate limits), count repos with recent updated_at


def get_repo_meta(owner, name):
    return rest_get_json(f"{API}/repos/{owner}/{name}") or {}

def repo_lang_bytes(owner, name):
    return rest_get_json(f"{API}/repos/{owner}/{name}/languages") or {}

# ---------- Processing ----------
def fold_notebooks_into_python(lang_bytes: dict):
    jb = lang_bytes.pop("Jupyter Notebook", 0)
    if jb:
        lang_bytes["Python"] = lang_bytes.get("Python", 0) + jb
    return lang_bytes

def to_percentages(lang_bytes: dict):
    total = sum(lang_bytes.values())
    if total == 0:
        return []
    items = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)
    return [{"name": k, "percent": round(v * 100.0 / total, 2), "bytes": v} for k, v in items]

def repo_entry(owner, meta, lang_bytes, readme_snippet=None):
    return {
        "repo": meta.get("name"),
        "owner": owner,
        "description": meta.get("description") or "",
        "language_percentages": to_percentages(lang_bytes),
        "primary_language": (max(lang_bytes, key=lang_bytes.get) if lang_bytes else None),
        "stars": meta.get("stargazers_count", 0),
        "updated_at": meta.get("updated_at"),
        "readme_snippet": readme_snippet,
    }

# ---------- Core summary ----------
def summarize_user(user):
    # quick existence check
    user_meta = rest_get_json(f"{API}/users/{user}")
    if user_meta is None or (isinstance(user_meta, dict) and user_meta.get("message") == "Not Found"):
        return {
            "username": user,
            "user_found": False,
            "message": "GitHub user not found or no public access",
            "overall_language_percentages": [],
            "top_repos": [],
            "repos": [],
        }

    authenticated = get_authenticated_login()
    per_repo = []
    overall_bytes = {}
    seen = set()

    if authenticated and authenticated.lower() == user.lower():
        # Same user as token owner: include owner + collaborator + org repos directly
        affiliated = list_affiliated_repos_for_self()
        for r in affiliated:
            owner = r.get("owner", {}).get("login") or user
            name = r["name"]
            key = f"{owner}/{name}"
            if key in seen:
                continue
            seen.add(key)

            meta = get_repo_meta(owner, name)
            if not meta:
                continue
            if meta.get("private") and not TOKEN:
                continue

            lbs = fold_notebooks_into_python(repo_lang_bytes(owner, name))
            for k, v in lbs.items():
                overall_bytes[k] = overall_bytes.get(k, 0) + int(v)
            readme = get_repo_readme(owner, name)
            per_repo.append(repo_entry(owner, meta, lbs, readme))
    else:
        # Different username: include public owned + contributed
        owned = list_owned_repos(user)
        for r in owned:
            owner = user
            name = r["name"]
            key = f"{owner}/{name}"
            if key in seen:
                continue
            seen.add(key)

            meta = get_repo_meta(owner, name)
            if not meta:
                continue
            lbs = fold_notebooks_into_python(repo_lang_bytes(owner, name))
            for k, v in lbs.items():
                overall_bytes[k] = overall_bytes.get(k, 0) + int(v)
            readme = get_repo_readme(owner, name)
            per_repo.append(repo_entry(owner, meta, lbs, readme))

        contributed = list_contributed_repos_graphql(user, first=100)
        if not contributed:
            # fallback to public recent events
            evs = list_contributed_repos_events(user, max_repos=30, max_pages=3)
            tmp = []
            for e in evs:
                m = get_repo_meta(e["owner"], e["name"])
                if m:
                    tmp.append({
                        "owner": e["owner"],
                        "name": e["name"],
                        "stargazers_count": m.get("stargazers_count", 0),
                        "updated_at": m.get("updated_at"),
                    })
            contributed = tmp

        for c in contributed:
            owner, name = c["owner"], c["name"]
            key = f"{owner}/{name}"
            if key in seen:
                continue
            seen.add(key)

            meta = get_repo_meta(owner, name)
            if not meta:
                continue
            if meta.get("private") and not TOKEN:
                continue

            lbs = fold_notebooks_into_python(repo_lang_bytes(owner, name))
            for k, v in lbs.items():
                overall_bytes[k] = overall_bytes.get(k, 0) + int(v)
            readme = get_repo_readme(owner, name)
            per_repo.append(repo_entry(owner, meta, lbs, readme))

    # Top 3 by stars desc, then updated_at desc
    per_repo_sorted = sorted(per_repo, key=lambda x: (x["stars"], x["updated_at"] or ""), reverse=True)
    top_repos = per_repo_sorted[:3]

    return {
        "username": user,
        "included_contributions": bool(TOKEN),
        "selection_strategy": "stars_then_recent",
        "overall_language_percentages": to_percentages(overall_bytes),
        "recent_pushes_30d": recent_pushes_30d(user),
        "top_repos": top_repos,
        "repos": per_repo,
    }

# ---------- CLI ----------
def main():
    if len(sys.argv) < 2:
        print("usage: python github_langs_all.py <github_username> [--out out.json]")
        sys.exit(1)

    username = sys.argv[1]
    out_path = None
    if len(sys.argv) >= 4 and sys.argv[2] == "--out":
        out_path = sys.argv[3]

    result = summarize_user(username)
    text = json.dumps(result, indent=2)
    print(text)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
            

if __name__ == "__main__":
    main()