# SkillSync (HackRU Fall 2025)

An AI-powered teammate-to-role matching tool that analyzes resumes and GitHub profiles, extracts ranked skills, and assigns the best person to each project role using Gemini embeddings and cosine similarity. The web app runs on Next.js (App Router) for the frontend and FastAPI for backend APIs.

## Highlights

- End-to-end pipeline from project planning → team intake → overview → role matching
- Skill extraction and role matching driven by Gemini embeddings (google.generativeai)
- Transparent matching: per-role candidate scores and concise logs in the UI
- Domain-aware amplifier: boosts alignment for domains like frontend, backend, finance, healthcare, etc.
- Tunable inputs: Top-K skills per category, category weighting, and softmax temperature for display separation
- Hygiene: local resume cache cleaned after processing

## Tech stack

- Frontend: Next.js (App Router), React, Tailwind, Shadcn UI
- Backend: FastAPI (Python), scikit-learn cosine similarity, NumPy
- Embeddings: Gemini models/embedding-001 via google.generativeai
- Misc: dotenv for keys, simple file-based resume cache

---

## Repository layout

```
.
├── CHANGELOG.md
├── README.md                # You are here
└── teamskills/
		├── components.json
		├── jsconfig.json
		# SkillSync – AI‑Powered Team Role Assignment
```
		SkillSync helps teams go from a rough idea to concrete roles and assignments in minutes. It:

		- Refines a free‑form project idea into actionable specifications with an AI planning chat
		- Gathers teammate info (names, GitHub, resumes) and extracts ranked skills via LLM + OCR
		- Derives exactly one complementary role per teammate based on the project spec
		- Matches people to roles using Gemini embeddings and cosine similarity, with transparent scoring

		The app is split into a Next.js frontend (App Router) and a FastAPI backend.

		## Features

		- End‑to‑end workflow: Planning → Team Input → Overview → Matching (state preserved between phases)
		- Resume + GitHub analysis: pdfplumber and Google Cloud Vision OCR for resumes; GitHub REST/GraphQL for repos
		- AI everywhere: Gemini 2.5 Flash Lite for planning/specs and for skill extraction; embeddings via models/embedding‑001
		- Transparent results: per‑role candidate ranking with raw cosine and softmax-enhanced scores, plus winner inputs
		- Domain awareness: optional anchor‑based boost nudges matches toward domain‑aligned candidates (frontend, backend, ML, etc.)
		- Tunable: Top‑K strongest items per category, category weighting, softmax temperature (display separation)
		- Hygiene: Frontend caches uploaded resumes under `.cache/resumes` and cleans up automatically after processing

		## Architecture

		```
		browser (Next.js App Router)
		  ├─ Phase 1: ProjectPlanningChat → POST /api/chat (Gemini via @google/genai)
		  │    └─ On confirmation → POST /api/extract-specifications  ┐
		  ├─ Phase 2: TeamInputForm                                    │ proxy → FastAPI
		  │    ├─ POST /api/upload-resume  (stores .cache/resumes)     │
		  │    ├─ POST /api/extract-roles                              │
		  │    └─ POST /api/process-team-data → backend /api/extract-skills
		  ├─ Phase 3: ProjectOverview (review + set Top‑K)
		  └─ Phase 4: RoleMatchResults → POST /api/match-roles → backend /api/match-roles

		FastAPI backend
		  ├─ /api/extract-specifications  (LLM: project spec JSON)
		  ├─ /api/extract-roles          (LLM: N complementary roles w/ core_skills)
		  ├─ /api/extract-skills         (resume OCR + GitHub → languages/skills/keywords)
		  ├─ /api/match-roles            (embeddings + cosine + domain boost → assignment)
		  └─ /resumes/*                  (serves stored resumes, if any)
		```

		### Repo layout

		```
		hackruf25/
		├─ CHANGELOG.md
		├─ team_members.json                              # simple backing store for backend
		└─ teamskills/
		   ├─ app/                                        # Next.js (App Router)
		   │  ├─ page.js                                  # phase orchestrator
		   │  ├─ layout.js, globals.css                   # UI shell & styles (Tailwind v4)
		   │  └─ api/                                     # server routes (Node runtime)
		   │     ├─ chat/route.js                         # calls @google/genai (Gemini) directly
		   │     ├─ upload-resume/route.js                # saves to .cache/resumes
		   │     ├─ cleanup-resumes/route.js              # clears cache
		   │     ├─ extract-specifications/route.js       # proxy → FastAPI
		   │     ├─ extract-roles/route.js                # proxy → FastAPI
		   │     └─ process-team-data/route.js            # proxy → FastAPI /api/extract-skills
		   ├─ components/                                 # UI components (shadcn‑style)
		   │  ├─ ProjectPlanningChat.jsx
		   │  ├─ TeamInputForm.jsx
		   │  ├─ ProjectOverview.jsx
		   │  ├─ RoleMatchResults.jsx
		   │  └─ ui/{button,card,dialog,input,label}.jsx
		   ├─ backend/                                    # FastAPI + analysis
		   │  ├─ app.py                                   # endpoints & orchestration
		   │  ├─ planning_extractor.py                    # LLM → specs & roles
		   │  ├─ role_matcher.py                          # embeddings + cosine + domain boost
		   │  ├─ skill_extractor.py                       # resumes + GitHub → skills
		   │  ├─ resume_scraper.py                        # pdfplumber + Vision OCR
		   │  ├─ github_scraper.py                        # REST/GraphQL + caching
		   │  ├─ path_utils.py                            # helpers (.cache paths)
		   │  └─ requirements.txt                         # backend deps
		   ├─ public/
		   ├─ next.config.mjs
		   └─ package.json                                # Next 15, React 19
		```

		## Requirements

		- Node.js LTS (18+ recommended) for the Next.js app
		- Python 3.11+ for the FastAPI backend
		- Poppler (for pdf2image) if you want OCR fallback on PDFs
		  - macOS: `brew install poppler`
		  - Linux: `apt-get install poppler-utils`
		  - Windows: install Poppler and add to PATH
		- Google Cloud Vision (optional but recommended for OCR)
		  - Set `GOOGLE_APPLICATION_CREDENTIALS` to your service account JSON
		- GitHub token (optional) to improve GitHub API limits and include private/affiliated repos

		## Environment variables

		Create `teamskills/.env.local` and set:

		- Frontend/Backend shared
		  - `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) – required for google.generativeai
		  - `NEXT_PUBLIC_BACKEND_URL` – FastAPI base URL for proxies (e.g. `http://localhost:8000`)
		- Backend only (read by FastAPI and scrapers)
		  - `GITHUB_TOKEN` – optional, increases GitHub rate limits and repo coverage
		  - `GITHUB_CACHE_TTL` – optional, seconds for GitHub readme cache (default 3600)
		  - `TOP_N` – optional, number of top repos to consider in summaries
		  - `GOOGLE_APPLICATION_CREDENTIALS` – optional path to Vision service account JSON

		Example `teamskills/.env.local`:

		```
		GEMINI_API_KEY=sk-...your-key...
		NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
		GITHUB_TOKEN=ghp_...optional...
		GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your-project-credentials.json
		```

		## Run locally

		1) Backend (FastAPI)

		- Create and activate a venv
		- Install dependencies
		- Start uvicorn

		Example (macOS, zsh):

		```bash
		cd teamskills/backend
		python3 -m venv .venv && source .venv/bin/activate
		pip install -r requirements.txt
		uvicorn app:app --reload --port 8000
		```

		2) Frontend (Next.js)

		- Install and run

		```bash
		cd teamskills
		npm install
		npm run dev
		```

		Open http://localhost:3000.

		## Usage walkthrough

		1) Planning (Phase 1)
		   - Describe your idea in the chat. When ready, click the provided confirmation button or type exactly:
		     - “Yes, I am ready to start delegating tasks.”
		   - This triggers spec extraction (title, summary, objectives, features, etc.).

		2) Team Input (Phase 2)
		   - Add teammates (name required), optionally a GitHub username, and upload a resume (PDF or image).
		   - On submit: resumes are cached locally, roles are derived for your team size, skills are extracted from resume + GitHub.

		3) Overview (Phase 3)
		   - Review the generated roles and each member’s languages/skills/keywords.
		   - Set Top‑K to limit strongest items per category used for matching.

		4) Matching (Phase 4)
		   - View role→person assignments with candidate bars (softmax‑enhanced on top of cosine).
		   - Winner’s top‑K inputs are shown for transparency.

		## API reference (summary)

		Frontend (Next.js) routes

		- POST `/api/chat` → { messages } → { content }
		- POST `/api/upload-resume` (form‑data: file, memberId, name) → { absPath, relPath, filename }
		- POST `/api/cleanup-resumes` → { success, deleted }
		- POST `/api/extract-specifications` → proxy to FastAPI `/api/extract-specifications`
		- POST `/api/extract-roles` → proxy to FastAPI `/api/extract-roles`
		- POST `/api/process-team-data` → proxy to FastAPI `/api/extract-skills`
		- POST `/api/match-roles` → proxy to FastAPI `/api/match-roles`

		Backend (FastAPI) routes

		- POST `/api/extract-specifications` → { success, data: specObject }
		- POST `/api/extract-roles` { specifications, memberCount } → { success, data: { roles: [...] } }
		- POST `/api/extract-skills` { members: [{ name, githubUsername, resumePath }], ... } → { success, data: { processed_members: [...] } }
		- POST `/api/match-roles` { roles, members, topK? } → { success, data: { assignments, similarity_matrix, reports, debug } }

		Notes

		- Matching uses role core_skills only for embeddings. Member text emphasizes skills/languages over keywords via weighting.
		- Domain boost (role_matcher.py) can be tuned via `DEFAULT_DOMAIN_ANCHORS`, `strength`, and `temperature`.

		## Troubleshooting

		- “GEMINI_API_KEY not configured”
		  - Ensure `teamskills/.env.local` has `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and restart backend.
		- OCR is weak or empty on PDFs
		  - Install Poppler and set Vision credentials for OCR fallback.
		- GitHub data seems sparse
		  - Add `GITHUB_TOKEN` to lift rate limits and include private/affiliated repos when permitted.
		- Proceed buttons disabled
		  - Editing planning/team inputs marks data as “dirty”; re‑generate/re‑process before proceeding.
		- Resume cache persisted
		  - Frontend calls `/api/cleanup-resumes` after successful processing. You can call it manually if needed.

		## Testing

		There are basic tests for scrapers and extraction logic in `teamskills/backend/`. To run them:

		```bash
		cd teamskills/backend
		python3 -m venv .venv && source .venv/bin/activate
		pip install -r requirements.txt pytest
		pytest -q
		```

		## License

		No license file was provided. If you intend to open‑source this project, consider adding a license.
