"""Run the daily *local* research pipeline from Windows Task Scheduler.

No cloud worker. Runs only while Windows is awake and signed in.
Official TWSE monthly data is available without a FinMind token for listed
four-digit stock symbols. Initial backfill is deliberately sequential.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys

from quantlab.v2.api import ForecastRequest, execute
from quantlab.v2.journal import save_forecast, mature_forecasts, scorecard
from quantlab.v2.storage import check_symbol
from quantlab.v2.twse import refresh_twse, last_allowed_session_date, TZ

WATCHLIST = Path(os.environ.get("QUANTLAB_V21_WATCHLIST", "data/v2/watchlist.json"))


def load_watchlist(path: Path = WATCHLIST) -> list[str]:
    if not path.exists():
        return ["2330"]  # conservative demonstration only, not all Taiwan stocks
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not 1 <= len(data) <= 30:
        raise ValueError("觀察清單必須是 1～30 檔股票代號的 JSON 陣列。")
    items = list(dict.fromkeys(check_symbol(str(x)) for x in data))
    if any(len(x) != 4 or not x.isdigit() for x in items):
        raise ValueError("TWSE 自動更新僅支援四位數上市股票代號。")
    return items


def run_daily(symbols: list[str], *, years: int = 4,
              horizons=(1, 5, 20), paths: int = 500) -> dict:
    outcome = {"date": datetime.now(TZ).isoformat(),
               "mode": "official_listed_stock_daily", "stocks": [], "errors": []}
    for symbol in symbols:
        try:
            refreshed = refresh_twse(symbol, years=years)
            stock = {"symbol": symbol, "update": refreshed, "predictions": []}
            for horizon in horizons:
                try:
                    forecast = execute(ForecastRequest(
                        symbol=symbol, source="db", horizon=horizon,
                        paths=paths, seed=19))
                    saved = save_forecast(forecast)
                    stock["predictions"].append(
                        {"horizon": horizon, "as_of": forecast["as_of"],
                         "journal": saved})
                except Exception as e:
                    stock["predictions"].append(
                        {"horizon": horizon, "error": str(e)[:250]})
                    outcome["errors"].append({"symbol": symbol,
                                              "horizon": horizon, "error": str(e)[:250]})
            outcome["stocks"].append(stock)
        except Exception as e:
            outcome["errors"].append({"symbol": symbol, "error": str(e)[:250]})
    outcome["evaluation"] = mature_forecasts()
    outcome["scorecard"] = scorecard()
    return outcome


def main():
    p = argparse.ArgumentParser(description="V2.1 real market data + immutable research snapshots")
    p.add_argument("--symbols", default=None,
                   help="Comma-separated TWSE listed symbols; default watchlist JSON or 2330")
    p.add_argument("--years", type=int, default=4)
    p.add_argument("--paths", type=int, default=500)
    p.add_argument("--horizons", type=str, default="1,5,20")
    args = p.parse_args()
    syms = ([check_symbol(x) for x in args.symbols.split(",") if x.strip()]
            if args.symbols else load_watchlist())
    if len(syms) > 30 or len(syms) == 0:
        p.error("symbols 必須介於 1～30 檔。")
    horizons = tuple(int(x) for x in args.horizons.split(","))
    if any(h not in (1, 5, 20, 60) for h in horizons):
        p.error("horizons 只支援 1,5,20,60。")
    report = run_daily(syms, years=args.years, paths=args.paths, horizons=horizons)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if report["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
