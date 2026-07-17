"""The JSON error envelope holds even for unexpected server-side failures."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_unhandled_exceptions_keep_the_json_error_envelope() -> None:
    # An app whose lifespan never ran has no store, so get_store raises a
    # RuntimeError deep inside the request - the client must still see the
    # envelope, not starlette's text/plain 500.
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/api/health")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "Internal server error"
