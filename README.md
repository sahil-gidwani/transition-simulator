# Precedent

Transfer valuations, backed by named precedent. Precedent answers the question a club owner
actually asks — "if we sign this player, what happens to their value?" — with evidence: real,
named players who made comparable moves, and what happened to their market value in the
12 months after.

## Quickstart

### Dev

```bash
# Client tooling + git hooks (Node 22 is pinned via Volta)
npm install

# Server (fetches Python 3.12 automatically)
cd server && uv sync && cd ..

# Terminal 1 - API on :8000
cd server && uv run uvicorn app.main:app --reload

# Terminal 2 - client on :5173 (proxies /api to the server)
npm run dev -w client
```

Open http://localhost:5173. Environment variables are documented in `.env.example`;
everything defaults sanely with no `.env` present.

### Docker

Coming soon — `docker compose up` will bring up the full app with zero manual steps.

## Methodology

_To be written: how comparable transitions are selected, how the value range and confidence
tier are derived, and the exact definition of the 12-month horizon._
