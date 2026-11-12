from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from quantlab.v2 import twse
from quantlab.v2.storage import read_prices, latest_date


FIELDS = ["日期", "成交股數", "成交金額", "開盤價", "最高價",
          "最低價", "收盤價", "漲跌價差", "成交筆數"]


def payload(day="115/11/11"):
    return {"stat": "OK", "fields": FIELDS,
            "data": [[day, "20,000", "2,000,000", "100.00",
                      "103.00", "99.00", "102.00", "+2", "2,500"]]}


def test_parse_official_roc_date_and_columns():
    parsed = twse.parse_stock_day(payload(), "2330", date(2026, 11, 11))
    assert len(parsed) == 1
    assert parsed["date"].iloc[0].date() == date(2026, 11, 11)
    assert parsed["volume"].iloc[0] == 20000
    assert parsed["close"].iloc[0] == 102.0


def test_refuse_unfinished_day_and_unexpected_schema():
    parsed = twse.parse_stock_day(payload(), "2330", date(2026, 11, 10))
    assert parsed.empty
    with pytest.raises(twse.TWSEError):
        twse.parse_stock_day({"stat": "OK", "fields": ["日期"], "data": []},
                             "2330", date(2026, 11, 11))
    with pytest.raises(twse.TWSEError):
        twse.parse_stock_day({"stat": "ERROR RATE LIMITED"}, "2330",
                             date(2026, 11, 11))
    assert twse.parse_stock_day({"stat": "查無資料"}, "2330", date(2026, 11, 11)).empty


def test_taipei_cutoff():
    zone = ZoneInfo("Asia/Taipei")
    early = datetime(2026, 11, 12, 10, 30, tzinfo=zone)
    after = datetime(2026, 11, 12, 18, 1, tzinfo=zone)
    assert twse.last_allowed_session_date(early) == date(2026, 11, 11)
    assert twse.last_allowed_session_date(after) == date(2026, 11, 12)


def test_month_starts_december_rollover():
    assert list(twse.month_starts(date(2025, 11, 15), date(2026, 2, 2))) == [
        date(2025, 11, 1), date(2025, 12, 1),
        date(2026, 1, 1), date(2026, 2, 1)]


def test_refresh_official_idempotent_and_incremental(tmp_path, monkeypatch):
    db = tmp_path / "quotes.duckdb"
    observed = []

    def fake_fetch(symbol, month, until, session=None):
        observed.append(month)
        if month.year == 2026 and month.month == 11:
            return twse.parse_stock_day(payload(), symbol, until)
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    monkeypatch.setattr(twse, "fetch_month", fake_fetch)
    now = datetime(2026, 11, 12, 18, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    first = twse.refresh_twse("2330", db_path=db, now=now,
                              years=1, pause_seconds=0)
    assert first["updated_rows"] == 1
    assert first["source"] == "twse_official"
    assert latest_date("2330", db) == date(2026, 11, 11)
    first_month_count = len(observed)
    observed.clear()
    second = twse.refresh_twse("2330", db_path=db, now=now,
                               years=1, pause_seconds=0)
    assert second["updated_rows"] == 1
    assert len(observed) < first_month_count
    assert len(read_prices("2330", db)) == 1
    with pytest.raises(ValueError):
        twse.refresh_twse("6488", db_path=db, years=0)


def test_no_fake_success_if_upstream_fails(tmp_path, monkeypatch):
    db = tmp_path / "quotes.duckdb"
    def broken(*args, **kwargs):
        raise twse.TWSEError("rate limited")
    monkeypatch.setattr(twse, "fetch_month", broken)
    now = datetime(2026, 11, 12, 18, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    with pytest.raises(twse.TWSEError):
        twse.refresh_twse("2330", db_path=db, now=now, years=1, pause_seconds=0)
    assert latest_date("2330", db) is None
