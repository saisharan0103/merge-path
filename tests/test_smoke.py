"""Boot + auth + simple CRUD smoke tests."""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_root(client):
    r = client.get("/")
    j = r.json()
    assert j["name"] == "PatchPilot"


def test_auth_me_returns_seed_user(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == 1
    assert j["has_pat"] is False


def test_repos_list_empty(client):
    r = client.get("/api/v1/repos")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "page_size": 50}


def test_metrics_overview_empty(client):
    r = client.get("/api/v1/metrics/overview")
    assert r.status_code == 200
    j = r.json()
    assert j["total_repos"] == 0
    assert j["merge_rate"] == 0


def test_strategy_summary_empty(client):
    r = client.get("/api/v1/strategy/summary")
    assert r.status_code == 200
    assert r.json()["green"] == 0
