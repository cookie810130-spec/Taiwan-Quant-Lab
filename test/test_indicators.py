import pandas as pd
import pytest
from quantlab.data.sample import make_sample_data
from quantlab.indicators import add_indicators, normalize_ohlcv


def test_sample_data_is_deterministic_and_valid():
    a = make_sample_data("2024-01-01", "2024-06-30", "2330")
    b = make_sample_data("2024-01-01", "2024-06-30", "2330")
    pd.testing.assert_frame_equal(a, b)
    assert {"date", "open", "high", "low", "close", "volume"} <= set(a.columns)
    assert (a["close"] > 0).all()


def test_indicators_columns_and_ranges():
    frame = make_sample_data("2023-01-01", "2025-01-01")
    out = add_indicators(frame, 20, 60)
    assert {"ma_fast", "ma_slow", "rsi", "macd", "macd_signal", "macd_hist"} <= set(out.columns)
    valid_rsi = out["rsi"].dropna()
    assert ((valid_rsi >= 0) & (valid_rsi <= 100)).all()


def test_invalid_moving_average_parameters():
    frame = make_sample_data("2023-01-01", "2024-01-01")
    with pytest.raises(ValueError):
        add_indicators(frame, 60, 20)


def test_normalize_rejects_missing_columns():
    with pytest.raises(ValueError):
        normalize_ohlcv(pd.DataFrame({"date": ["2024-01-01"], "close": [10]}))
