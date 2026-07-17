"""Offline build pipeline: raw datasets -> lean processed parquet artifacts.

Run from server/ with the data dependency group installed:

    uv run python -m pipeline.build

The pipeline reads server/data/raw/ (see scripts/download_data.py), enforces
hard audit gates (source pin, row counts, valuation freshness, funnel parity)
and writes server/data/processed/ plus meta.json and docs/pipeline-report.md.
It fails loudly - non-zero exit, no partial artifacts - when any gate regresses.
"""
