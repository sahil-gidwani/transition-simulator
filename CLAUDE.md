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
6. **Stated similarity.** The definition of "similar" (position group, age band, value bracket, origin league tier band, a continuous destination league strength band, club value percentile + Elo where available — terciles are display-only) is explicit in the README and applied uniformly.
7. **Real data only.** Every player, value, comp and stat shown by the product comes from the processed real datasets — no placeholder, synthetic or invented data ever ships in the API or UI. (Synthetic data lives exclusively in test fixtures.) Stale upstream data is surfaced (values carry an as-of date), never papered over.
8. **Evaluated, not asserted.** The comps engine's range and confidence tiers are validated by a temporal backtest (coverage, interval width, pinball loss vs naive baselines) with a leakage-safe, date-exact comp-availability rule; distance weights carry provenance from that backtest.

## Stack & layout

- `client/` — Vite + React + TypeScript (strict), Tailwind, TanStack Query, Recharts, React Router. Tests: Vitest + React Testing Library.
- `server/` — FastAPI + Python 3.12, managed with **uv**. Lint/format: ruff. Types: mypy (CI-blocking). Tests: pytest.
  - `app/api/routes/` — thin handlers only: no logic, no data access.
  - `app/services/` — all domain logic: `comps.py` (matching + relaxation), `valuation.py` (range + confidence), `percentiles.py`, `narrative.py` (deterministic templates, no LLM), plus `players.py`/`destinations.py`/`simulation.py` (read services + orchestrator) and `constants.py` (every retrieval/valuation tunable; the retrieval weights/ladder/pool size are tuned by the temporal backtest — the provenance docstring carries the method, seed and config hash, and any retune must update it).
  - `app/repositories/` — the ONLY code that touches data files (processed parquet, loaded once via the lifespan into a `DataStore`; tests inject synthetic stores through `create_app(store=...)`).
  - `app/core/` — cross-cutting plumbing: settings, injectable `Clock` (defaults to the system date — staleness is surfaced via as-of dates and caveats, never hidden by pinning time), the shared error surface (`{"error": {code, message, detail}}`; simulating a player with no valuation is a 409 `player_without_value`), search-text normalization.
  - `app/schemas/` — Pydantic request/response models.
  - `pipeline/` — offline build: raw data → `data/processed/` artifacts.
  - `pipeline/eval/` — the offline temporal backtest + tuning harness (`uv run python -m pipeline.eval <stage>`); it **deliberately imports `app.services`** to evaluate the shipped engine, and writes raw records to `server/data/eval/` (gitignored). The committed deliverables are `docs/eval-report.md` and the tuned constants. Tuning never writes into `app/` — the winning config is frozen by hand in a reviewed commit.
  - **`app/` never imports `pipeline/`** — the serving contract is `data/processed/*.parquet` + `meta.json` (shared constants like `season_min` are read from `meta.json`, not from pipeline code).
- `docs/` — the docs map is `docs/README.md`. `pipeline-report.md` and `eval-report.md` are **generated** (change `pipeline/report.py` / `pipeline/eval`, never the files). Every claim has exactly one home doc — others link to it. Docs are updated in the same commit as the behavior they describe.
- Root `package.json` — npm workspaces; husky + lint-staged + commitlint live here.
- `docker-compose.yml` — `docker compose up` brings up the full app with zero manual steps (processed data ships in the repo).

## Commands

- Root: `npm install` (hooks + client deps).
- Client (in `client/`): `npm run dev` / `build` / `test` / `lint`.
- Server (in `server/`): `uv sync` · `uv run uvicorn app.main:app --reload` · `uv run pytest` · `uv run ruff check .` · `uv run mypy app`.
- Pipeline (in `server/`): `uv run python -m pipeline.build` (requires raw data in `server/data/raw/` — see README).
- Backtest (in `server/`, needs the `eval` group from `uv sync`): `uv run python -m pipeline.eval all` reproduces the post-freeze evaluation; `tune` is the pre-freeze search whose output is frozen by hand (see `docs/eval-report.md` → Reproducibility).
- Docker: `docker compose up --build`.

## Data

- Primary: "Football Data from Transfermarkt" (the `davidcariboo/player-scores` dataset), acquired via the Hugging Face mirror `ngeorgea/transfermarkt-player-scores` **pinned at a specific revision** → `server/data/raw/` (gitignored). The pipeline records the pinned revision and enforces hard audit gates (row counts, valuation freshness, funnel size) because upstream builds have shipped regressions — see `docs/data-notes.md` for the pinned revision, gate results and audit numbers. Coverage: first-tier leagues (~30 countries), games/appearances 2012+, valuations 2000+. Transfers carry no loan flag (loans parse to fee=0 like free transfers) — loans are detected structurally and excluded from the comps universe.
- Club/league strength is **derived, multi-factor**: squad values computed from `player_valuations` aggregation (the upstream clubs table's market-value field is unreliable) → league strength (ln median squad value) + display tiers (fixed ln-strength thresholds with two-season hysteresis) + per-club `club_value_pct` (within-league squad-value percentile, 1.0 = richest; terciles survive for display copy only); ClubElo history (via public mirrors; credited to clubelo.com) adds an as-of-date Elo percentile for European clubs only — non-UEFA leagues are structurally excluded from automatic Elo mapping — with a flagged fallback where unavailable. League membership per season is games-derived where match data exists; the current-day snapshot fallback survives only for league-seasons with no games at all (`league_source`), and league stats below an 8-club membership floor are null, flagged via `stats_valid`.
- Enrichment shipped: ClubElo rating history (above) plus two ID bridges inside the Elo mapping ladder — the reep cross-provider register (CC0) and an Opta→ClubElo team-name mapping. Understat xG and EA FC attributes were scoped in the data research and deliberately deferred (`docs/future-scope.md`); the engine uses no per-performance features in matching.
- Processed: `server/data/processed/` — lean parquet (7 artifacts incl. `player_values.parquet`, the full per-player valuation history behind profile charts), committed; the only thing the server reads. The served app performs **no network calls at runtime**; data acquisition is an offline pipeline concern (some steps may require an unrestricted network).
- Glossary: **transition** = historical transfer with known value before and after · **v_before** = last valuation ≤180 days strictly before the transfer (transfer-day revaluations excluded) · **v_after** = valuation nearest +12 months (6–18 window) · **v_after_date** = when that valuation happened (drives the backtest availability rule) · **multiplier** = v_after / v_before · **comp** = a transition matched to a query · **relaxation ladder** = staged filter-widening when comps are scarce, always surfaced in `pool_quality` · **strength** = ln(median derived squad value) per league-season · **strength-band filter** = the destination hard filter |comp `to_strength` − destination strength| ≤ band; the band widens on the ladder (labelled) and is never dropped · **league tier** = 1–4 display bucket from fixed ln-strength thresholds with two-season hysteresis (display + origin-filter semantics only; null below the 8-club floor) · **club_value_pct** = squad-value percentile within league-season, 1.0 = richest (the engine's club term) · **club tercile** = top/mid/bottom third by squad value (display copy only) · **minutes_share_pre** = share of possible league minutes in the 365 days pre-transfer (partial playing-time control).

## Engineering conventions

- Conventional Commits (commitlint-enforced). Small, focused commits at each coherent step. Never `--no-verify` — fix the issue.
- TypeScript strict, no unexplained `any`. Python fully type-hinted including internals.
- Tests required for: comp matching (filters, ranking, relaxation), value-range math, narrative assembly, tricky UI logic (formatters, simulator states). Use small synthetic fixtures, never real data.
- All docs, comments, commits and UI copy are product-first for a public repo: Precedent is a standalone product — no company names, no assignment language.
- Never commit: `.env`, `server/data/raw/`, root-level PDFs, `PROMPTS.md`.
