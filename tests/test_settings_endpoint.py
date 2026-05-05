"""/settings endpoints."""

from __future__ import annotations


def test_get_settings_default(client):
    r = client.get("/api/v1/settings")
    j = r.json()
    assert j["github_pat_set"] is False
    assert j["pause_all"] is False
    assert j["codex_healthy"] is True


def test_update_settings(client):
    r = client.put("/api/v1/settings", json={"buffer_multiplier": 3.0, "pause_all": True})
    j = r.json()
    assert j["buffer_multiplier"] == 3.0
    assert j["pause_all"] is True


def test_save_pat_ok(client, monkeypatch):
    def ok(self):
        return {"login": "myname"}
    monkeypatch.setattr("app.services.github_client.GitHubClient.get_authenticated_user", ok)
    r = client.put("/api/v1/settings/pat", json={"github_pat": "ghp_test"})
    assert r.status_code == 200
    assert r.json()["github_username"] == "myname"
