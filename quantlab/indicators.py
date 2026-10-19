import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize OHLCV columns used by the app."""
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"缺少必要欄位：{', '.join(sorted(missing))}")
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    out = out.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if (out[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("價格欄位必須大於 0。")
    return out


def add_indicators(frame: pd.DataFrame, fast_ma: int = 20, slow_ma: int = 60) -> pd.DataFrame:
    if fast_ma < 2 or slow_ma <= fast_ma:
        raise ValueError("均線參數必須符合 2 <= fast_ma < slow_ma。")
    out = normalize_ohlcv(frame)
    close = out["close"]
    out["ma_fast"] = close.rolling(fast_ma, min_periods=fast_ma).mean()
    out["ma_slow"] = close.rolling(slow_ma, min_periods=slow_ma).mean()
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["rsi"] = 100 - (100 / (1 + rs))
    out.loc[(avg_loss == 0) & (avg_gain > 0), "rsi"] = 100
    out.loc[(avg_gain == 0) & (avg_loss > 0), "rsi"] = 0
    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False, min_periods=9).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    return out
