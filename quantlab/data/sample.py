import hashlib
import numpy as np
import pandas as pd


def make_sample_data(start_date, end_date, symbol: str = "2330") -> pd.DataFrame:
    """Generate deterministic synthetic OHLCV data (not real Taiwan stock prices)."""
    dates = pd.bdate_range(start=pd.Timestamp(start_date), end=pd.Timestamp(end_date))
    if len(dates) == 0:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    seed = int(hashlib.sha256(str(symbol).encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.00035, 0.018, len(dates))
    # Add a mild trend cycle so charts contain varied regimes.
    cycle = 0.0004 * np.sin(np.arange(len(dates)) / 22)
    close = 100 * np.exp(np.cumsum(returns + cycle))
    open_prices = close * (1 + rng.normal(0, 0.006, len(dates)))
    high = np.maximum(open_prices, close) * (1 + rng.uniform(0.001, 0.018, len(dates)))
    low = np.minimum(open_prices, close) * (1 - rng.uniform(0.001, 0.018, len(dates)))
    volume = rng.integers(1_000_000, 30_000_000, len(dates))
    return pd.DataFrame({
        "date": dates,
        "open": np.round(open_prices, 2),
        "high": np.round(high, 2),
        "low": np.round(low, 2),
        "close": np.round(close, 2),
        "volume": volume.astype("int64"),
    })
