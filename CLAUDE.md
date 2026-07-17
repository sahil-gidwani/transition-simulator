# Precedent

Transfer valuations, backed by named precedent. Precedent answers the question a club owner actually asks — "if we sign this player, what happens to their value?" — with evidence: real, named players who made comparable moves, and what happened to their market value in the 12 months after.

## Product surface

1. **Search** — find any in-scope player; results show position, age, club, league, market value.
2. **Profile** (`/players/:id`) — bio, market-value history, performance percentiles vs same position + league peers.
3. **Transition Simulator** (`/players/:id/simulate`) — pick a destination league (optionally a club) → predicted 12-month value range with a stated confidence level, a panel of named comparable transitions (before/after), and a plain-language scout's read.

## Non-negotiable product principles

Correctness requirements, not style preferences — violating one is a bug:

1. **Named precedent over black box.** Every prediction must be traceable to the comps shown on screen.
2. **No survivorship bias.** Comps are selected by similarity only, never by outcome. Decliners are shown, in red.
3. **Ranges, never false precision.** Output is a range + confidence tier (High/Medium/Low/Insufficient) driven by pool size and dispersion.
4. **Small N is said out loud.** Thin pools are labelled ("expanded search", "insufficient precedent"); with <2 usable comps there is NO range at all.
5. **One consistent horizon.** "Value after" = valuation nearest to 12 months post-transfer within a 6–18 month window — for every comp, everywhere.
6. **Stated similarity.** The definition of "similar" (position group, age band, value bracket, league tier derived from squad values, club tercile) is explicit in the README and applied uniformly.

## Stack & layout

- `client/` — Vite + React + TypeScript (strict), Tailwind, TanStack Query, Recharts, React Router. Tests: Vitest + React Testing Library.
- `server/` — FastAPI + Python 3.12, managed with **uv**. Lint/format: ruff. Types: mypy (CI-blocking). Tests: pytest.
  - `app/api/routes/` — thin handlers only: no logic, no data access.
  - `app/services/` — all domain logic: `comps.py` (matching + relaxation), `valuation.py` (range + confidence), `percentiles.py`, `narrative.py` (deterministic templates, no LLM).
  - `app/repositories/` — the ONLY code that touches data files (processed parquet, loaded at startup).
  - `app/schemas/` — Pydantic request/response models.
  - `pipeline/` — offline build: raw data → `data/processed/` artifacts.
- Root `package.json` — npm workspaces; husky + lint-staged + commitlint live here.
- `docker-compose.yml` — `docker compose up` brings up the full app with zero manual steps (processed data ships in the repo).

## Commands

- Root: `npm install` (hooks + client deps).
- Client (in `client/`): `npm run dev` / `build` / `test` / `lint`.
- Server (in `server/`): `uv sync` · `uv run uvicorn app.main:app --reload` · `uv run pytest` · `uv run ruff check .` · `uv run mypy app`.
- Pipeline (in `server/`): `uv run python -m pipeline.build` (requires raw data in `server/data/raw/` — see README).
- Docker: `docker compose up --build`.

## Data

- Raw: Kaggle "Football Data from Transfermarkt" (`davidcariboo/player-scores`) → `server/data/raw/` (gitignored).
- Processed: `server/data/processed/` — lean parquet, committed; the only thing the server reads.
- Glossary: **transition** = historical transfer with known value before and after · **v_before** = last valuation ≤6 months pre-transfer · **v_after** = valuation nearest +12 months (6–18 window) · **multiplier** = v_after / v_before · **comp** = a transition matched to a query · **relaxation ladder** = staged filter-widening when comps are scarce, always surfaced in `pool_quality` · **league tier** = 1–4 bucket from log median club squad value · **club tercile** = squad-value rank within league-season (top/mid/bottom).

## Engineering conventions

- Conventional Commits (commitlint-enforced). Small, focused commits at each coherent step. Never `--no-verify` — fix the issue.
- TypeScript strict, no unexplained `any`. Python fully type-hinted including internals.
- Tests required for: comp matching (filters, ranking, relaxation), value-range math, narrative assembly, tricky UI logic (formatters, simulator states). Use small synthetic fixtures, never real data.
- All docs, comments, commits and UI copy are product-first for a public repo: Precedent is a standalone product — no company names, no assignment language.
- Never commit: `.env`, `server/data/raw/`, root-level PDFs, `PROMPTS.md`.
