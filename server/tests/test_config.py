from pathlib import Path

from app.core.config import Settings


def test_defaults_require_no_env() -> None:
    settings = Settings(_env_file=None)

    assert settings.port == 8000
    assert settings.data_dir == Path("data/processed")
