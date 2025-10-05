#!/usr/bin/env python3
"""
Run analyze_profile for GitHub user 'ayushmish605' and a resume found in
teamskills/.cache/resumes using the same import/exec pattern as the one-liner
the user provided.
"""
import sys, json, importlib
from pathlib import Path


def main() -> int:
    repo = Path('/Users/rachitasaini/Desktop/My Projects/hackruf25')
    # Ensure repo root is on sys.path for package imports
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    # Map absolute imports expected by skill_extractor to package modules
    mod_gs = importlib.import_module('teamskills.backend.github_scraper')
    sys.modules['github_scraper'] = mod_gs
    mod_rs = importlib.import_module('teamskills.backend.resume_scraper')
    sys.modules['resume_scraper'] = mod_rs

    sx = importlib.import_module('teamskills.backend.skill_extractor')

    # Locate a resume in teamskills/.cache/resumes
    resumes = repo / 'teamskills' / '.cache' / 'resumes'
    patterns = ('*.pdf','*.png','*.jpg','*.jpeg','*.txt','*')
    candidates = sum([sorted(list(resumes.glob(p))) for p in patterns], []) if resumes.exists() else []
    resume = (candidates[0] if candidates else None)

    print('Using resume:', resume)
    res = sx.analyze_profile(
        github_username='ayushmish605',
        resume_path=(str(resume) if resume else None),
        max_repos=5,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
