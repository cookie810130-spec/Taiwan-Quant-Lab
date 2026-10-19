import pandas as pd
import pytest
from quantlab.data.sample import make_sample_data
from quantlab.indicators import add_indicators
from quantlab.strategy import generate_signals
from quantlab.backtest import run_backtest


def test_strategy_signals_are_boolean():
    frame = add_indicators(make_sample_data("2022-01-01", "2025-01-01"), 20, 60)
    out = generate_signals(frame)
    assert out["entry_signal"].dtype == bool
    assert out["exit_signal"].dtype == bool


def test_backtest_returns_metrics_and_equity():
    frame = add_indicators(make_sample_data("2022-01-01", "2025-01-01"), 20, 60)
    frame = generate_signals(frame)
    result = run_backtest(frame, initial_cash=100_000)
    assert len(result.equity_curve) == len(frame)
    assert result.metrics["initial_cash"] == 100_000
    assert result.metrics["final_equity"] > 0
    assert "max_drawdown" in result.metrics


def test_backtest_rejects_invalid_cash():
    frame = add_indicators(make_sample_data("2022-01-01", "2025-01-01"), 20, 60)
    with pytest.raises(ValueError):
        run_backtest(frame, initial_cash=0)


def test_empty_backtest_rejected():
    with pytest.raises(ValueError):
        run_backtest(pd.DataFrame(), initial_cash=100_000)
