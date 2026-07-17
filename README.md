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

# Both dev servers in one command: client on :5173, API on :8000
npm run dev
```

Or run them separately: `npm run dev -w client` and `npm run dev:api`. Other root scripts:
`npm run test`, `npm run lint`, `npm run typecheck` — each covers client and server.

Open http://localhost:5173. Environment variables are documented in `.env.example`;
everything defaults sanely with no `.env` present.

### Docker

Coming soon — `docker compose up` will bring up the full app with zero manual steps.

## Methodology

_To be written: how comparable transitions are selected, how the value range and confidence
tier are derived, and the exact definition of the 12-month horizon._
