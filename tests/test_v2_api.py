import os
from fastapi.testclient import TestClient
from quantlab.v2.api import app, jobs


def test_auth_and_health(monkeypatch):
    monkeypatch.setenv("QUANTLAB_API_KEY", "test_key_that_is_long_enough_123456")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v2/info").status_code == 401
    headers = {"X-API-Key": "test_key_that_is_long_enough_123456"}
    assert client.get("/api/v2/info", headers=headers).status_code == 200
    resp = client.post("/api/v2/forecast", headers=headers,
                       json={"symbol": "2330", "source": "demo",
                             "horizon": 5, "paths": 250, "seed": 7})
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["synthetic_data"] is True
    assert result["horizon_trading_days"] == 5


def test_reject_invalid_source_and_period(monkeypatch):
    monkeypatch.setenv("QUANTLAB_API_KEY", "test_key_that_is_long_enough_123456")
    client = TestClient(app)
    headers = {"X-API-Key": "test_key_that_is_long_enough_123456"}
    assert client.post("/api/v2/forecast", headers=headers,
                       json={"source": "surprise"}).status_code == 422
    assert client.post("/api/v2/forecast", headers=headers,
                       json={"source": "demo", "horizon": 2}).status_code == 422
    assert client.post("/api/v2/forecast", headers=headers,
                       json={"source": "db", "symbol": "../bad"}).status_code == 422
