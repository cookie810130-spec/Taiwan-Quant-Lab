import requests
import pandas as pd


class FinMindError(RuntimeError):
    pass


def fetch_finmind_prices(stock_id: str, start_date: str, end_date: str, token: str) -> pd.DataFrame:
    """Fetch daily TaiwanStockPrice data through FinMind API v4."""
    if not stock_id or not stock_id.isdigit():
        raise FinMindError("股票代號請輸入數字，例如 2330。")
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
        "token": token,
    }
    try:
        response = requests.get(url, params=params, timeout=(5, 25))
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise FinMindError(f"API 連線失敗：{exc}") from exc
    except ValueError as exc:
        raise FinMindError("API 回傳不是有效 JSON。") from exc
    if payload.get("status") not in (200, "200", True):
        raise FinMindError(str(payload.get("msg") or payload.get("message") or "API 回傳錯誤"))
    rows = payload.get("data", [])
    if not rows:
        raise FinMindError("查無資料，請檢查股票代號、日期區間、Token 或 API 額度。")
    frame = pd.DataFrame(rows)
    mapping = {
        "date": "date",
        "open": "open",
        "max": "high",
        "min": "low",
        "close": "close",
        "Trading_Volume": "volume",
    }
    missing = set(mapping) - set(frame.columns)
    if missing:
        raise FinMindError(f"API 欄位不完整：{', '.join(sorted(missing))}")
    out = frame[list(mapping)].rename(columns=mapping)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna().sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return out
