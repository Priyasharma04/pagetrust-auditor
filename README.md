# PageTrust Auditor

It crawls a public URL, audits buttons/clickable elements, extracts local-business details, checks semantic copy alignment, flags contradictions and unsupported claims, scores trust risk, and generates an improvement prompt plus JSON/PDF exports.

## Quick start

### 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium 
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`.

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.



1. Paste a generated local business website URL.
2. Add business type and city/location.
3. Run audit.
4. Show the trust score, high-priority issues, clickable audit table, and generated improvement prompt.
5. Export PDF/JSON.

