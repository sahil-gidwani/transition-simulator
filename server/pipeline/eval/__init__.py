"""Offline evaluation & tuning: the temporal backtest behind the comps engine.

Never in the serving path. Run from server/:

    uv run python -m pipeline.eval all

This package deliberately imports app.services - it evaluates the shipped
retrieval engine as-is, so the numbers in docs/eval-report.md describe the
exact code that serves. The forbidden import direction remains app -> pipeline.
Raw outputs land in server/data/eval/ (gitignored, reproducible); the committed
deliverables are docs/eval-report.md and the tuned constants in
app/services/constants.py.
"""
