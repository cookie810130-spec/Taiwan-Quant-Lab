"""Local DuckDB OHLCV store with provenance and deduplication."""
from __future__ import annotations
import os
from pathlib import Path
import re

import pandas as pd
from quantlab.indicators import normalize_ohlcv

DEFAULT_DB = Path(os.environ.get("QUANTLAB_V2_DB", "data/v2/quantlab.duckdb"))
SYMBOL_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,19}$")


def check_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(symbol) or ".." in symbol:
        raise ValueError("股票代號格式無效。")
    return symbol


def _connect(db_path=None):
    import duckdb
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    conn.execute("""
      CREATE TABLE IF NOT EXISTS daily_prices (
        symbol VARCHAR NOT NULL,
        date DATE NOT NULL,
        open DOUBLE NOT NULL,
        high DOUBLE NOT NULL,
        low DOUBLE NOT NULL,
        close DOUBLE NOT NULL,
        volume BIGINT NOT NULL,
        provenance VARCHAR NOT NULL,
        PRIMARY KEY (symbol, date)
      )
    """)
    return conn


def import_csv(symbol: str, csv_path: str, db_path=None) -> dict:
    """Import locally supplied real CSV; never infer that CSV is official."""
    symbol = check_symbol(symbol)
    frame = normalize_ohlcv(pd.read_csv(csv_path, encoding="utf-8-sig"))
    if frame.empty:
        raise ValueError("CSV 沒有有效的 OHLCV 行情。")
    rows = [(symbol, row.date.date(), float(row.open), float(row.high),
             float(row.low), float(row.close), int(row.volume),
             "user_csv_unverified") for row in frame.itertuples(index=False)]
    conn = _connect(db_path)
    try:
        conn.executemany("""
          INSERT OR REPLACE INTO daily_prices
          (symbol, date, open, high, low, close, volume, provenance)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()
    finally:
        conn.close()
    return {"symbol": symbol, "imported_rows": len(rows), "provenance": "user_csv_unverified"}


def read_prices(symbol: str, db_path=None) -> pd.DataFrame:
    symbol = check_symbol(symbol)
    # No side-effect of creating empty database merely to read.
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    if not path.exists():
        raise FileNotFoundError("尚未建立資料庫；請先匯入 OHLCV CSV。")
    conn = _connect(path)
    try:
        frame = conn.execute("""
          SELECT date, open, high, low, close, volume FROM daily_prices
          WHERE symbol = ? ORDER BY date
        """, [symbol]).df()
    finally:
        conn.close()
    if frame.empty:
        raise ValueError("本機資料庫沒有這個股票代號，請先匯入 CSV。")
    return normalize_ohlcv(frame)


def list_symbols(db_path=None) -> list[dict]:
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    if not path.exists():
        return []
    conn = _connect(path)
    try:
        rows = conn.execute("""
          SELECT symbol, COUNT(*) AS rows, MIN(date) AS start_date,
                 MAX(date) AS end_date, MIN(provenance) AS provenance
          FROM daily_prices GROUP BY symbol ORDER BY symbol
        """).fetchall()
    finally:
        conn.close()
    return [{"symbol": a, "rows": b, "start_date": str(c), "end_date": str(d),
             "provenance": e} for a, b, c, d, e in rows]
