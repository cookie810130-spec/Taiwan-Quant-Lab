"""Authenticated FastAPI control plane for Windows Python + Android.

Bind to 127.0.0.1 and expose privately with Tailscale Serve HTTPS.
Only simulation/research endpoints; no orders or live trading.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hmac
import os
from threading import Lock
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from quantlab.v2.data import get_prices
from quantlab.v2.forecast import predict_scenarios
from quantlab.v2.storage import list_symbols, check_symbol

app = FastAPI(title="Taiwan Quant Lab V2", version="2.0.0-alpha",
              description="Research-only, private Tailscale API")
jobs: dict[str, dict] = {}
jobs_lock = Lock()
workers = ThreadPoolExecutor(max_workers=2)


def require_key(x_api_key: str | None = Header(None)):
    expected = os.environ.get("QUANTLAB_API_KEY", "")
    if not expected or len(expected) < 24:
        raise HTTPException(status_code=503, detail="API key is not configured.")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key.")


class ForecastRequest(BaseModel):
    symbol: str = Field(default="2330", min_length=1, max_length=20)
    source: str = Field(default="demo", pattern="^(demo|db|finmind)$")
    horizon: int = Field(default=20)
    paths: int = Field(default=1000, ge=250, le=5000)
    seed: int = Field(default=19, ge=0, le=2**32 - 1)


def execute(request: ForecastRequest) -> dict:
    if request.horizon not in (1, 5, 20, 60):
        raise ValueError("horizon 僅支援 1、5、20、60。")
    symbol = check_symbol(request.symbol)
    frame, provenance = get_prices(symbol, request.source)
    return predict_scenarios(frame, symbol, "demo" if request.source == "demo" else provenance,
                             request.horizon, request.paths, request.seed)


@app.get("/health")
def health():
    return {"status": "ok", "product": "Taiwan-Quant-Lab", "version": "v2-alpha"}


@app.get("/api/v2/info", dependencies=[Depends(require_key)])
def info():
    return {"version": "2.0.0-alpha", "research_only": True,
            "data_sources": ["demo", "db", "finmind"],
            "models": ["conditional_block_bootstrap", "logistic_regression"],
            "no_live_broker_orders": True}


@app.get("/api/v2/data/symbols", dependencies=[Depends(require_key)])
def symbols():
    return {"symbols": list_symbols()}


@app.post("/api/v2/forecast", dependencies=[Depends(require_key)])
def forecast(request: ForecastRequest):
    try:
        return execute(request)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        # Internal errors are logged server-side, never expose credential details.
        import logging
        logging.exception("Forecast request failed")
        raise HTTPException(status_code=500, detail="預測計算失敗，請查看伺服器日誌。") from e


def _task(job_id: str, request: ForecastRequest):
    try:
        result = execute(request)
        record = {"status": "done", "result": result}
    except Exception as e:
        record = {"status": "failed", "error": str(e)[:300]}
    with jobs_lock:
        jobs[job_id].update(record)
        jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


@app.post("/api/v2/jobs/forecast", dependencies=[Depends(require_key)])
def submit_forecast(request: ForecastRequest):
    with jobs_lock:
        # Avoid unbounded in-memory jobs. Jobs are deliberately volatile in alpha.
        if len(jobs) >= 100:
            raise HTTPException(status_code=429, detail="排程記錄已滿；請重新啟動服務或稍後處理。")
        job_id = str(uuid4())
        jobs[job_id] = {"id": job_id, "status": "queued",
                        "created_at": datetime.now(timezone.utc).isoformat()}
    workers.submit(_task, job_id, request)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/v2/jobs/{job_id}", dependencies=[Depends(require_key)])
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="找不到任務（重啟會清除 alpha 版暫存任務）。")
        return dict(job)
