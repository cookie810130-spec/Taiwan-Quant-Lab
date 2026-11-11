"""Explicit data source selection, synthetic demo is never mistaken for live."""
from __future__ import annotations

from datetime import date, timedelta
import os

from quantlab.data.sample import make_sample_data
from quantlab.data.finmind import fetch_finmind_prices
from quantlab.v2.storage import check_symbol, read_prices


def get_prices(symbol: str, source: str):
    symbol = check_symbol(symbol)
    if source == "demo":
        frame = make_sample_data(date.today() - timedelta(days=4 * 365),
                                 date.today(), symbol)
        return frame, "demo"
    if source == "db":
        return read_prices(symbol), "db_user_csv_unverified"
    if source == "finmind":
        token = os.environ.get("FINMIND_TOKEN", "").strip()
        if not token:
            raise ValueError("缺少 FINMIND_TOKEN；請勿把 Token 放進 APK 或程式碼。")
        return fetch_finmind_prices(symbol,
                                    (date.today() - timedelta(days=4 * 365)).isoformat(),
                                    date.today().isoformat(), token), "finmind"
    raise ValueError("不支援的資料來源（demo／db／finmind）。")
