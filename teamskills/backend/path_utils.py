from pathlib import Path


def teamskills_root() -> Path:
    """Return the absolute path to the teamskills project root (parent of backend)."""
    return Path(__file__).resolve().parents[1]


def cache_dir(name: str) -> Path:
    """Return teamskills/.cache/<name>, creating it if necessary."""
    d = teamskills_root() / ".cache" / name
    d.mkdir(parents=True, exist_ok=True)
    return d
