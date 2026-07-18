# Documentation map

Two reading paths, depending on why you're here:

- **Evaluating the methodology** — [methodology.md](methodology.md) →
  [eval-report.md](eval-report.md) → [data-notes.md](data-notes.md) →
  [decisions.md](decisions.md).
- **Extending the code** — [architecture.md](architecture.md) →
  [pipeline.md](pipeline.md) → [api.md](api.md) → [frontend.md](frontend.md).

| Doc | One line | Kind |
|---|---|---|
| [architecture.md](architecture.md) | System boundaries, request flow, cross-cutting plumbing, deployment | hand-written |
| [methodology.md](methodology.md) | The comps engine: filters, ladder, distance, range, confidence, club-level honesty | hand-written |
| [api.md](api.md) | All six endpoints with captured request/response examples | hand-written |
| [pipeline.md](pipeline.md) | Build stages, the funnel precisely, data dictionary, the eval harness | hand-written |
| [frontend.md](frontend.md) | Client data layer, simulator state machine, honesty register, design system | hand-written |
| [decisions.md](decisions.md) | The decision log, dated and commit-linked | hand-written |
| [future-scope.md](future-scope.md) | Deliberately deferred work, with evidence and landing paths | hand-written |
| [data-notes.md](data-notes.md) | Data acquisition, the audit, upstream defects, hardening stories | hand-written (audit record) |
| [eval-report.md](eval-report.md) | Backtest results: coverage, width, pinball vs baselines, tiers, tuning | **generated** by `pipeline.eval` |
| [pipeline-report.md](pipeline-report.md) | The current build: gates, funnel, artifacts, caveats | **generated** by `pipeline.build` |

Generated docs regenerate from code — never hand-edit them (for the pipeline report's
prose, edit `server/pipeline/report.py`). Every claim has one home doc; everything else
links to it, so if two docs seem to disagree, the one in the table above that *owns* the
topic wins and the other has a bug.
