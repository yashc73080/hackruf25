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
		├── next.config.mjs
		├── package.json
		├── postcss.config.mjs
		├── requirements.txt     # Frontend dev helper requirements (if any)
		├── app/
		│   ├── favicon.ico
		│   ├── globals.css
		│   ├── layout.js
		│   ├── page.js          # Phase orchestrator and routing across pages
		│   └── api/
		│       ├── chat/route.js
		│       ├── process-team-data/route.js
		│       └── match-roles/route.js  # Proxy to FastAPI role matcher
		├── backend/
		│   ├── app.py           # FastAPI app
		│   ├── gemini_helper.py
		│   ├── github_scraper.py
		│   ├── resume_scraper.py
		│   ├── role_matcher.py  # Embedding + cosine similarity + domain amplifier
		│   ├── requirements.txt # Python backend requirements
		│   ├── test_gemini_helper.py
		│   ├── test_github_scraper.py
		│   ├── test_resume_scraper.py
		│   └── (other tests / helpers)
		├── components/
		│   ├── ProjectPlanningChat.jsx
		│   ├── TeamInputForm.jsx
		│   ├── ProjectOverview.jsx
		│   ├── RoleMatchResults.jsx
		│   └── ui/          # Button, Card, Dialog, Input, etc.
		├── lib/
		│   └── utils.js
		└── public/
				├── file.svg
				├── globe.svg
				├── next.svg
				├── vercel.svg
				└── window.svg
```

---

## How it works: pipeline by phases

The app keeps all phases mounted and navigates between them while preserving state. Proceed buttons are enabled only when downstream prerequisites are valid.

### Phase 1: Project planning (ProjectPlanningChat)
- Objective: capture/iterate on the project idea and outputs like objectives, core features, and constraints.
- Behavior:
	- New chat messages mark planningDirty, which disables downstream proceed buttons until regeneration.
	- When specifications are generated, specsReady is set and the user can proceed to the team input phase.

### Phase 2: Team input (TeamInputForm)
- Objective: gather teammates’ names, GitHub usernames, and resumes; then process to build skill vectors.
- Steps on submit:
	1) Upload each resume to a local cache and record absolute paths.
	2) Derive roles for the team size from the specifications.
	3) Process team data (scrape GitHub and parse resumes) to extract ranked arrays of skills, languages, and keywords.
	4) Normalize member shapes for the frontend.
	5) Cleanup local resume cache to avoid stale files.
- Proceed logic: Proceed is disabled if planningDirty, teamDirty, or teamReady is false. Editing the team sets teamDirty and disables downstream proceeds until re-processed.

### Phase 3: Project overview (ProjectOverview)
- Objective: review the project idea, roles, and team profiles; set Top-K tuning before matching.
- Key UI elements:
	- Back and Proceed buttons in the card header, consistently styled and spaced.
	- Roles accordion with: Purpose, Responsibilities, Core Skills, Nice to Have, Collaboration Notes.
	- Member cards with Programming Languages, Technical Skills, and Notable Keywords.
	- Top-K control: choose how many strongest items per category (skills/languages/keywords) are considered.
- Proceed logic: disabled if planningDirty or teamDirty or team not ready.
- Match trigger: clicking “Match roles to members” (or header Proceed) calls Next.js API which proxies to FastAPI.

### Phase 4: Role matching results (RoleMatchResults)
- Objective: assign people to roles with transparent scoring.
- Backend algorithm (role_matcher.py):
	- Normalize roles to core_skills-only text for embedding.
	- Normalize members to top-k arrays (skills/languages/keywords) and build embedding text with category weighting.
	- Embeddings via Gemini models/embedding-001.
	- Base similarity: cosine(role, member).
	- Domain-aware amplifier: optional anchor-based alignment (frontend/backend/finance/healthcare/etc.) scales similarity up for same-domain matches and down for mismatches.
	- Greedy assignment per role using the boosted similarities.
	- UI readiness: returns per-role candidates with raw cosine and a softmax-enhanced score (cos*).
- UI rendering:
	- For each role:
		- Shows bolded “Core skills:” summary derived from role debug.
		- “Assigned to: <Name>” in indigo.
		- A vertical list of horizontal bars (one per candidate), sorted by cos* descending.
		- Bar width and color are driven by cos* (green near 1, red near 0). Label shows only (cos* …).
		- Winner’s Top-K inputs listed beneath (skills, languages, keywords) from backend debug.
	- A per-role log line summarizes the top match.
- Tuning knobs:
	- topK (Phase 3 UI) controls how many strongest items per category are used for members.
	- Backend weights can emphasize skills/languages over keywords.
	- domain_boost controls anchor selection, strength, and temperature.
	- softmax_temperature controls display separation.

---

## Configuration

- Environment variables (placed in `teamskills/.env.local`):
	- GEMINI_API_KEY (or GOOGLE_API_KEY): required for google.generativeai
- Backend requirements (`teamskills/backend/requirements.txt`): install in a virtualenv.
- Frontend Node version: use an LTS Node (see `teamskills/package.json`).

---

## Running locally

1) Backend (FastAPI)
- Create and activate a Python 3.11+ virtual environment
- Install requirements
- Set GEMINI_API_KEY (or GOOGLE_API_KEY) in `teamskills/.env.local`
- Start FastAPI server (e.g., uvicorn)

2) Frontend (Next.js)
- Install dependencies with your preferred package manager
- Run the Next.js dev server

Optional: open http://localhost:3000 in your browser.

### Example minimal steps (macOS, zsh)

```bash
# Backend
cd teamskills/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Ensure teamskills/.env.local has GEMINI_API_KEY
uvicorn app:app --reload --port 8000

# Frontend (new terminal)
cd teamskills
npm install
npm run dev
```

Frontend runs on http://localhost:3000 and proxies API calls to the FastAPI server endpoints you configure.

---

## Troubleshooting

- No matches or bars look identical
	- Increase topK in Phase 3 or adjust softmax_temperature in the backend match call.
	- Consider enabling domain_boost for clearer separation across domains.
- Gemini key issues
	- Ensure GEMINI_API_KEY (or GOOGLE_API_KEY) is present in teamskills/.env.local.
	- Restart the backend after changing environment variables.
- Resume cache not cleared
	- The cleanup route removes `.cache/resumes` under the Next.js working dir; verify permissions and path.
- Proceed buttons disabled
	- If you edit planning or team inputs, downstream proceeds are disabled until you re-generate/re-process.

---

## Notes and next steps
- Add a small UI control in Phase 3 to toggle domain_boost and tune its strength.
- Persist topK and softmax settings per run for reproducibility.
- Add tests around role matching weights and domain anchors.