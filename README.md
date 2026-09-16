# Learning CRM

Rule-based learner CRM using React + Vite, FastAPI, SQLAlchemy and PostgreSQL.

Read `HANDOFF.md` before making changes.

## Current business model

- IGC = course
- IDP = program/family, not a course
- ID1, ID2, ID3 = separate independent courses inside IDP
- Stage-1 unique learner key = `learner_number`
- Recommendations/opportunities are Python rules, not ML
- Every dated course event is preserved

## Start

Backend:

```powershell
cd .\backend
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\seed_courses.py
uvicorn app.main:app --reload
```

Frontend in another PowerShell:

```powershell
cd .\frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

API docs: http://127.0.0.1:8000/docs
