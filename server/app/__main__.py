"""Dev entrypoint: `uv run python -m app` (run from server/ so reload watches it)."""

import uvicorn

from app.core.config import get_settings


def main() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=get_settings().port, reload=True)


if __name__ == "__main__":
    main()
