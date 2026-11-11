"""Immutable real-data forecast journal and out-of-sample maturation.

One prediction per (symbol, observed as_of, horizon, model_version).
A prediction is only evaluated after horizon *observed sessions* exist.
Demo data are never journaled. Never backfill historical forecasts as if live.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from quantlab.v2.storage import _connect, DEFAULT_DB, check_symbol


MODEL_VERSION = "2.1-alpha-v2-bootstrap-logit"


def _schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS forecast_journal (
            id VARCHAR PRIMARY KEY,
            symbol VARCHAR NOT NULL,
            as_of DATE NOT NULL,
            horizon INTEGER NOT NULL,
            model_version VARCHAR NOT NULL,
            provenance VARCHAR NOT NULL,
            forecast_close DOUBLE NOT NULL,
            ml_up DOUBLE,
            sim_p05 DOUBLE NOT NULL,
            sim_p95 DOUBLE NOT NULL,
            payload_json VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            actual_date DATE,
            actual_close DOUBLE,
            realized_up BOOLEAN,
            brier DOUBLE,
            within_interval BOOLEAN,
            UNIQUE(symbol, as_of, horizon, model_version)
        )
    """)


def save_forecast(forecast: dict, db_path=None) -> dict:
    symbol = check_symbol(forecast["symbol"])
    if forecast.get("synthetic_data") or forecast.get("source") == "demo":
        raise ValueError("合成資料不得存入真實預測績效紀錄。")
    provenance = str(forecast.get("source", ""))
    if provenance not in ("twse_official", "finmind", "user_csv_unverified"):
        raise ValueError("請使用資料庫中的有來源標註行情，才能永久保存預測。")
    ml = forecast["ml_direction"]
    sim = forecast["simulation"]
    prob = ml.get("probability_up")
    if prob is not None and not 0 <= float(prob) <= 1:
        raise ValueError("方向機率超出範圍。")
    # Store the exact input-as-of and model output. Never overwrite an old snapshot.
    conn = _connect(db_path)
    try:
        _schema(conn)
        key = [symbol, forecast["as_of"], int(forecast["horizon_trading_days"]),
               MODEL_VERSION]
        existing = conn.execute("""
            SELECT id, created_at FROM forecast_journal
            WHERE symbol=? AND as_of=? AND horizon=? AND model_version=?
        """, key).fetchone()
        if existing:
            return {"id": existing[0], "created_at": existing[1].isoformat(),
                    "saved": False, "reason": "existing_prediction_kept_immutable"}
        uid = str(uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.execute("""
            INSERT INTO forecast_journal (
                id, symbol, as_of, horizon, model_version, provenance,
                forecast_close, ml_up, sim_p05, sim_p95, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [uid, *key, provenance, float(forecast["last_close"]), prob,
              float(sim["terminal_price_p05"]), float(sim["terminal_price_p95"]),
              json.dumps(forecast, ensure_ascii=False, allow_nan=False), now])
        return {"id": uid, "created_at": now.isoformat() + "Z",
                "saved": True, "reason": "new_immutable_prediction"}
    finally:
        conn.close()


def mature_forecasts(db_path=None) -> dict:
    """Score each pending forecast ONLY on the h-th observed trading bar after as_of.

    Does not fabricate business-day calendars and does not mark missing data as
    wrong. A revised historical data point changes the score only if it was
    not scored before; scores remain immutable.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    if not path.exists():
        return {"evaluated_now": 0, "pending": 0, "evaluated_total": 0}
    conn = _connect(path)
    try:
        _schema(conn)
        pending = conn.execute("""
            SELECT id, symbol, as_of, horizon, forecast_close, ml_up, sim_p05, sim_p95
            FROM forecast_journal WHERE actual_date IS NULL
            ORDER BY created_at
        """).fetchall()
        scored = 0
        for rid, symbol, as_of, h, base, prob, low, high in pending:
            # Verify the original prediction anchor exists in price history.
            anchor = conn.execute(
                "SELECT close FROM daily_prices WHERE symbol=? AND date=?",
                [symbol, as_of]).fetchone()
            if anchor is None:
                continue
            actual = conn.execute("""
                SELECT date, close FROM daily_prices
                WHERE symbol=? AND date>? ORDER BY date LIMIT 1 OFFSET ?
            """, [symbol, as_of, int(h) - 1]).fetchone()
            if actual is None:
                continue
            observed_date, observed_price = actual
            direction = bool(float(observed_price) > float(base))
            brier = (float(prob) - float(direction)) ** 2 if prob is not None else None
            coverage = bool(float(low) <= float(observed_price) <= float(high))
            conn.execute("""
                UPDATE forecast_journal
                SET actual_date=?, actual_close=?, realized_up=?, brier=?,
                    within_interval=? WHERE id=? AND actual_date IS NULL
            """, [observed_date, float(observed_price), direction, brier, coverage, rid])
            scored += 1
        totals = conn.execute("""
            SELECT COUNT(*),
              SUM(CASE WHEN actual_date IS NULL THEN 1 ELSE 0 END)
            FROM forecast_journal
        """).fetchone()
        return {"evaluated_now": scored,
                "pending": int(totals[1] or 0),
                "evaluated_total": int(totals[0] or 0) - int(totals[1] or 0),
                "method": "hth_observed_trading_session_after_as_of"}
    finally:
        conn.close()


def history(symbol: str | None = None, limit: int = 50, db_path=None) -> list[dict]:
    if not 1 <= limit <= 500:
        raise ValueError("limit 必須介於 1～500。")
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    if not path.exists():
        return []
    conn = _connect(path)
    try:
        _schema(conn)
        filter_sql = "WHERE symbol=?" if symbol else ""
        args = [check_symbol(symbol)] if symbol else []
        rows = conn.execute(f"""
            SELECT id, symbol, as_of, horizon, model_version, provenance,
                   forecast_close, ml_up, sim_p05, sim_p95, created_at,
                   actual_date, actual_close, realized_up, brier, within_interval
            FROM forecast_journal {filter_sql} ORDER BY created_at DESC LIMIT ?
        """, args + [limit]).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r[0], "symbol": r[1], "as_of": str(r[2]),
            "horizon": r[3], "model_version": r[4], "source": r[5],
            "forecast_close": r[6], "ml_probability_up": r[7],
            "sim_p05": r[8], "sim_p95": r[9],
            "created_at": r[10].isoformat() + "Z",
            "actual_date": str(r[11]) if r[11] else None,
            "actual_close": r[12], "realized_up": r[13], "brier": r[14],
            "within_interval": r[15],
            "status": "evaluated" if r[11] else "pending",
        })
    return result


def scorecard(db_path=None) -> dict:
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    if not path.exists():
        return {"count_evaluated": 0, "count_pending": 0, "horizons": []}
    conn = _connect(path)
    try:
        _schema(conn)
        pending = int(conn.execute(
            "SELECT COUNT(*) FROM forecast_journal WHERE actual_date IS NULL").fetchone()[0])
        rows = conn.execute("""
            SELECT horizon, COUNT(*) AS count,
                   COUNT(ml_up) AS n_probability,
                   AVG(brier) AS brier_score,
                   AVG(CASE WHEN ml_up IS NOT NULL THEN
                       CASE WHEN (ml_up >= 0.5)=realized_up THEN 1.0 ELSE 0.0 END
                       ELSE NULL END) AS direction_accuracy,
                   AVG(CASE WHEN within_interval THEN 1.0 ELSE 0.0 END) AS interval_coverage
            FROM forecast_journal WHERE actual_date IS NOT NULL
            GROUP BY horizon ORDER BY horizon
        """).fetchall()
    finally:
        conn.close()
    return {
        "count_evaluated": int(sum(r[1] for r in rows)), "count_pending": pending,
        "horizons": [{"trading_days": r[0], "evaluated": r[1], "ml_samples": r[2],
                      "ml_brier": r[3], "ml_direction_accuracy": r[4],
                      "simulation_interval_coverage": r[5]} for r in rows],
        "warnings": [
            "僅有預測發布後才實際發生的交易日會被驗證；無歷史預測回填。",
            "評分不代表 AI 有超額報酬能力，Brier 越低越好；樣本數不足時不應據此交易。",
            "P05-P95 區間為未校準模擬輸出，實際覆蓋率不保證為90%。",
        ],
    }
