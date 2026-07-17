from api_factories import make_build_info, make_client, make_store


def test_health_returns_status_version_and_build_info() -> None:
    store = make_store(build_info=make_build_info(revision="pinned123"))
    response = make_client(store).get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str)
    assert body["version"]
    assert body["data"]["repo"] == "example/mirror"
    assert body["data"]["revision"] == "pinned123"
    assert body["data"]["max_valuation_date"] == "2026-06-12"
    assert body["data"]["censor_horizon"] == "2025-12-14"
    assert body["data"]["comps_universe_size"] == 19_407
