# UnifyOps — AI Industrial Knowledge Intelligence Platform

> Unified Asset & Operations Brain for industrial plants.

UnifyOps ingests every category of document a heavy-industrial plant produces and turns them into a single, continuously-updating knowledge graph. On top of that one substrate, it runs four intelligence layers: an Expert Knowledge Copilot, a Maintenance Intelligence & RCA Agent, a Quality & Regulatory Compliance layer, and a Lessons Learned & Failure Intelligence Engine.

---

## Project Structure

```
UnifyOps/
├── frontend/          # Next.js 15 (App Router, TypeScript)
├── backend/           # FastAPI (Python 3.12)
├── .github/workflows/ # CI/CD via GitHub Actions
├── .gitignore
├── .gitleaks.toml     # Secret scanning config
├── PRD_V1.md          # Product Requirements Document
└── README.md
```

---

## Getting Started

### Prerequisites

- **Node.js** 20+
- **Python** 3.12+
- **npm** (comes with Node.js)

### Backend (FastAPI)

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API is available at **http://localhost:8000**
- Swagger docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

The app is available at **http://localhost:3000**

### Running Tests

```bash
# Backend
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v

# Frontend
cd frontend
npm run lint
```

---

## Environment Variables

### Frontend (`frontend/.env.local`)

Copy `frontend/.env.example` to `frontend/.env.local` and fill in your Firebase config:

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Firebase Web API Key |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Firebase Auth Domain |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | Firebase Project ID |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | Firebase Storage Bucket |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | Firebase Sender ID |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | Firebase App ID |
| `NEXT_PUBLIC_API_URL` | Backend API URL (default: `http://localhost:8000`) |

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env`.

---

## CI/CD

GitHub Actions workflows run automatically on push/PR:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci-frontend.yml` | Changes to `frontend/` | Lint, type check, build |
| `ci-backend.yml` | Changes to `backend/` | Lint (ruff), type check (mypy), test (pytest) |
| `ci-full.yml` | Push/PR to `main` | Secret scanning (gitleaks) + both pipelines |

---

## Architecture

See [PRD_V1.md](PRD_V1.md) for the full architecture, data model, and implementation roadmap.

**Current phase: Phase 0 — Foundation & Platform Bootstrap**

---

## License

Proprietary. All rights reserved.
