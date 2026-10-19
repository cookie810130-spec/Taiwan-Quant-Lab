import pandas as pd


def generate_signals(frame: pd.DataFrame, rsi_min: float = 40, rsi_max: float = 70) -> pd.DataFrame:
    """Create end-of-day entry/exit signals; execution occurs on the next session."""
    if rsi_min >= rsi_max:
        raise ValueError("rsi_min 必須小於 rsi_max。")
    out = frame.copy()
    valid = out[["ma_fast", "ma_slow", "rsi", "macd", "macd_signal"]].notna().all(axis=1)
    bullish = (out["ma_fast"] > out["ma_slow"]) & out["rsi"].between(rsi_min, rsi_max) & (out["macd"] > out["macd_signal"])
    bearish = (out["ma_fast"] < out["ma_slow"]) | (out["macd"] < out["macd_signal"]) | (out["rsi"] < rsi_min)
    out["entry_signal"] = (valid & bullish).fillna(False)
    out["exit_signal"] = (valid & bearish).fillna(False)
    return out
