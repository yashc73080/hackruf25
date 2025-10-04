import os, sys, json, requests
from dotenv import load_dotenv

# ---------------- Setup ----------------
load_dotenv()
API = "https://api.github.com"
GITHUB_GRAPHQL = f"{API}/graphql"
TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
REST_HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

def get_json(url):
    r = requests.get(url, headers=REST_HEADERS)
    if r.status_code == 200:
        return r.json()
    return None

def post_graphql(query, variables=None):
    if not TOKEN:
        return None
    payload = {"query": query, "variables": variables or {}}
    r = requests.post(GITHUB_GRAPHQL, headers=HEADERS, json=payload)
    if r.status_code == 200:
        j = r.json()
        if "errors" in j:
            return None
        return j
    return None

# ---------------- Owned repos (REST) ----------------
def list_owned_repos(user):
    # user's own public repos
    url = f"{API}/users/{user}/repos?per_page=100&type=owner&sort=updated"
    return get_json(url) or []

# ---------------- Contributed repos (GraphQL preferred) ----------------
def list_contributed_repos_graphql(user, first=100):
    """
    Uses GraphQL to fetch repositories the user contributed to (public).
    Requires a token. Returns list of dicts with owner, name, stars, updated_at.
    """
    if not TOKEN:
        return []
    query = """
    query($login: String!, $first: Int!) {
      user(login: $login) {
        contributionsCollection {
          repositoriesContributedTo(first: $first, includeUserRepositories: true) {
            nodes {
              nameWithOwner
              stargazerCount
              updatedAt
              isFork
            }
          }
        }
      }
    }
    """
    data = post_graphql(query, {"login": user, "first": first})
    if not data:
        return []
    nodes = data.get("data", {}).get("user", {}) \
                .get("contributionsCollection", {}) \
                .get("repositoriesContributedTo", {}) \
                .get("nodes", []) or []
    out = []
    for n in nodes:
        full = n.get("nameWithOwner", "")
        if "/" in full:
            owner, name = full.split("/", 1)
            out.append({
                "owner": owner,
                "name": name,
                "stargazers_count": n.get("stargazerCount", 0),
                "updated_at": n.get("updatedAt"),
            })
    return out

# ---------------- Contributed repos (fallback via Events) ----------------
def list_contributed_repos_events(user, max_repos=30, max_pages=3):
    """
    Fallback: recent public PushEvents to capture recent collabs.
    Returns list of {owner, name}. Stars/updated_at will be filled via repo meta call.
    """
    repos = []
    seen = set()
    for page in range(1, max_pages + 1):
        url = f"{API}/users/{user}/events/public?per_page=100&page={page}"
        r = requests.get(url, headers=REST_HEADERS)
        if r.status_code != 200:
            break
        events = r.json()
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

# ---------------- Repo meta & languages ----------------
def get_repo_meta(owner, name):
    url = f"{API}/repos/{owner}/{name}"
    return get_json(url) or {}

def repo_lang_bytes(owner, name):
    url = f"{API}/repos/{owner}/{name}/languages"
    return get_json(url) or {}

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

def repo_entry(owner, meta, lang_bytes):
    return {
        "repo": meta.get("name"),
        "owner": owner,
        "description": meta.get("description") or "",
        "language_percentages": to_percentages(lang_bytes),
        "primary_language": (max(lang_bytes, key=lang_bytes.get) if lang_bytes else None),
        "stars": meta.get("stargazers_count", 0),
        "updated_at": meta.get("updated_at"),
    }

# ---------------- Summarize ----------------
def summarize_user(user):
    # 1) owned repos (REST provides all meta we need)
    owned_raw = list_owned_repos(user)

    # 2) contributed repos
    collab = list_contributed_repos_graphql(user, first=100)
    if not collab:
        # fallback to Events if GraphQL unavailable
        collab_simple = list_contributed_repos_events(user, max_repos=30, max_pages=3)
        # fill meta via REST
        filled = []
        for c in collab_simple:
            meta = get_repo_meta(c["owner"], c["name"])
            if meta:
                filled.append({
                    "owner": c["owner"],
                    "name": c["name"],
                    "stargazers_count": meta.get("stargazers_count", 0),
                    "updated_at": meta.get("updated_at")
                })
        collab = filled

    # 3) merge (dedupe by owner/name)
    seen = set()
    all_repos = []

    # owned
    for r in owned_raw:
        owner = user
        name = r["name"]
        key = f"{owner}/{name}"
        if key in seen: 
            continue
        seen.add(key)
        all_repos.append({
            "owner": owner,
            "name": name,
            "stargazers_count": r.get("stargazers_count", 0),
            "updated_at": r.get("updated_at"),
            "description": r.get("description") or ""
        })

    # contributed
    for c in collab:
        owner = c.get("owner")
        name = c.get("name")
        if not owner or not name:
            continue
        key = f"{owner}/{name}"
        if key in seen:
            continue
        seen.add(key)
        all_repos.append({
            "owner": owner,
            "name": name,
            "stargazers_count": c.get("stargazers_count", 0),
            "updated_at": c.get("updated_at"),
            "description": ""  # will be filled by meta if needed
        })

    # 4) build per-repo entries with languages & ensure meta is complete
    overall_bytes = {}
    per_repo = []
    for item in all_repos:
        owner = item["owner"]
        name = item["name"]

        # fetch meta if description missing (for contributed ones)
        meta = get_repo_meta(owner, name)
        desc = meta.get("description") if meta else item.get("description", "")
        stars = meta.get("stargazers_count", item.get("stargazers_count", 0))
        updated_at = meta.get("updated_at", item.get("updated_at"))

        lbs = fold_notebooks_into_python(repo_lang_bytes(owner, name))
        for k, v in lbs.items():
            overall_bytes[k] = overall_bytes.get(k, 0) + int(v)

        per_repo.append({
            "repo": name,
            "owner": owner,
            "description": desc or "",
            "language_percentages": to_percentages(lbs),
            "primary_language": (max(lbs, key=lbs.get) if lbs else None),
            "stars": stars or 0,
            "updated_at": updated_at
        })

    # 5) top 3: by stars desc, then updated_at desc (tie-break)
    per_repo_sorted = sorted(
        per_repo,
        key=lambda x: (x["stars"], x["updated_at"] or ""),
        reverse=True
    )
    top_repos = per_repo_sorted[:3]

    return {
        "username": user,
        "included_collaborations": True,
        "overall_language_percentages": to_percentages(overall_bytes),
        "selection_strategy": "stars_then_recent",
        "top_repos": top_repos,
        "repos": per_repo  # full list for flexibility
    }

# ---------------- CLI ----------------
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