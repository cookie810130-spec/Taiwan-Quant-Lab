"""Official TWSE monthly STOCK_DAY collector (listed stocks only).

Source: https://www.twse.com.tw/exchangeReport/STOCK_DAY
No key required. Does NOT cover TPEx or intraday quotes.
No unverified trading bar for today's unfinished session is imported.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo
import re
import time as clock

import pandas as pd
import requests

from quantlab.indicators import normalize_ohlcv
from quantlab.v2.storage import check_symbol, latest_date, upsert_prices

ENDPOINT = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
TZ = ZoneInfo("Asia/Taipei")
LISTED_SYMBOL = re.compile(r"^[0-9]{4}$")
EMPTY_RESPONSES = ("查無資料", "沒有符合", "無符合", "無資料", "no data")


class TWSEError(RuntimeError):
    pass


def last_allowed_session_date(now: datetime | None = None) -> date:
    """Today's official final close is accepted only after 17:00 Taiwan time."""
    now = now or datetime.now(TZ)
    now = now.astimezone(TZ) if now.tzinfo else now.replace(tzinfo=TZ)
    return now.date() if now.time() >= time(17, 0) else now.date() - timedelta(days=1)


def month_starts(first: date, last: date):
    current = date(first.year, first.month, 1)
    while current <= last:
        yield current
        current = date(current.year + (current.month == 12),
                       1 if current.month == 12 else current.month + 1, 1)


def parse_stock_day(payload: dict, symbol: str, until: date) -> pd.DataFrame:
    """Official ROC date + indexed data columns; fail rather than silently shift fields."""
    if not isinstance(payload, dict):
        raise TWSEError("TWSE JSON 格式異常。")
    stat = str(payload.get("stat", ""))
    if stat != "OK":
        if any(word.lower() in stat.lower() for word in EMPTY_RESPONSES):
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        raise TWSEError(f"TWSE 回傳非成功狀態：{stat[:150]}")
    required = ("日期", "成交股數", "開盤價", "最高價", "最低價", "收盤價")
    fields = payload.get("fields")
    rows = payload.get("data")
    if not isinstance(fields, list) or not isinstance(rows, list):
        raise TWSEError("TWSE 缺少 fields / data。")
    try:
        positions = [fields.index(field) for field in required]
    except ValueError as e:
        raise TWSEError("TWSE 表格欄位格式已改變，拒絕匯入。") from e

    def number(value):
        if value is None:
            return None
        s = str(value).replace(",", "").strip()
        return float(s) if s not in ("", "--", "---", "X", "-") else None

    out = []
    for row in rows:
        if not isinstance(row, list) or len(row) < len(fields):
            raise TWSEError("TWSE 資料列長度錯誤。")
        raw = [row[i] for i in positions]
        d = str(raw[0]).split("/")
        if len(d) != 3:
            raise TWSEError("TWSE 民國日期格式改變。")
        try:
            day = date(int(d[0]) + 1911, int(d[1]), int(d[2]))
            volume, o, h, l, c = [number(v) for v in raw[1:]]
        except (ValueError, TypeError) as e:
            raise TWSEError("TWSE 日期或價格無法轉換。") from e
        if day > until or None in (volume, o, h, l, c):
            continue
        if min(o, h, l, c) <= 0 or volume < 0 or h < max(o, c, l) or l > min(o, c, h):
            raise TWSEError(f"TWSE {symbol} {day} OHLCV 資料不合理。")
        out.append({"date": pd.Timestamp(day), "open": o, "high": h,
                    "low": l, "close": c, "volume": int(volume)})
    if not out:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    return normalize_ohlcv(pd.DataFrame(out))


def fetch_month(symbol: str, month: date, until: date, *, session=None) -> pd.DataFrame:
    sym = check_symbol(symbol)
    if not LISTED_SYMBOL.fullmatch(sym):
        raise ValueError("TWSE 官方 STOCK_DAY 僅支援四位數上市股票代號。")
    client = session or requests
    params = {"response": "json", "date": month.strftime("%Y%m%d"), "stockNo": sym}
    last_error = None
    for attempt in range(3):
        try:
            response = client.get(ENDPOINT, params=params,
                                  headers={"User-Agent": "TaiwanQuantLab/2.1 personal research"},
                                  timeout=25)
            response.raise_for_status()
            return parse_stock_day(response.json(), sym, until)
        except (requests.RequestException, ValueError) as e:
            last_error = e
            if attempt < 2:
                clock.sleep(1 + attempt * 2)
    raise TWSEError(f"TWSE {sym} {month:%Y-%m} 無法下載：{last_error}") from last_error


def refresh_twse(symbol: str, *, years: int = 4, db_path=None,
                 now: datetime | None = None, session=None,
                 pause_seconds: float = 0.35) -> dict:
    """Incremental import; requery 45 days to pick up late revisions.

    No writes occur until all expected monthly requests return successfully.
    If the latest month is genuinely not published yet, it contributes zero rows.
    """
    sym = check_symbol(symbol)
    if not LISTED_SYMBOL.fullmatch(sym):
        raise ValueError("TWSE 僅支援四位數上市股票；上櫃請使用 FinMind。")
    if not 1 <= years <= 10:
        raise ValueError("初次回補年數必須介於 1～10。")
    if not 0 <= pause_seconds <= 10:
        raise ValueError("pause_seconds 不合理。")
    until = last_allowed_session_date(now)
    last_stored = latest_date(sym, db_path)
    start = (last_stored - timedelta(days=45) if last_stored
             else until - timedelta(days=365 * years + 14))
    start = max(start, date(2010, 1, 4))
    if start > until:
        return {"symbol": sym, "downloaded_rows": 0, "updated_rows": 0,
                "latest_date": str(last_stored), "source": "twse_official", "status": "up_to_date"}
    frames = []
    months = list(month_starts(start, until))
    for i, month in enumerate(months):
        frame = fetch_month(sym, month, until, session=session)
        if not frame.empty:
            frames.append(frame[frame["date"] >= pd.Timestamp(start)])
        if pause_seconds and i < len(months) - 1:
            clock.sleep(pause_seconds)
    if not frames:
        return {"symbol": sym, "downloaded_rows": 0, "updated_rows": 0,
                "latest_date": str(last_stored) if last_stored else None,
                "source": "twse_official", "status": "no_new_data"}
    data = normalize_ohlcv(pd.concat(frames, ignore_index=True))
    count = upsert_prices(sym, data, "twse_official", db_path)
    newest = latest_date(sym, db_path)
    return {"symbol": sym, "downloaded_rows": int(len(data)), "updated_rows": count,
            "latest_date": str(newest), "source": "twse_official",
            "status": "ok", "months_queried": len(months),
            "notice": "上市股票官方未還原日線；非即時、未包含上櫃或除權息還原。"}
