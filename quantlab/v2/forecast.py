"""Reproducible, conditional-market bootstrap + machine-learning direction forecast.

The simulation is a historical-scenario sampler, NOT a calibrated forecast.
The ML classifier is evaluated on chronological held-out observations.
Neither component proves a trading edge or assures future returns.
"""
from __future__ import annotations

from datetime import date
import math

import numpy as np
import pandas as pd

from quantlab.indicators import normalize_ohlcv


def _features(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["close"].astype(float)
    ret = close.pct_change()
    volume = frame["volume"].astype(float)
    log_ret = np.log(close).diff()
    return pd.DataFrame({
        "return_1": ret,
        "return_5": close.pct_change(5),
        "return_20": close.pct_change(20),
        "return_60": close.pct_change(60),
        "volatility_10": log_ret.rolling(10).std(),
        "volatility_20": log_ret.rolling(20).std(),
        "volume_ratio": volume / volume.rolling(20).mean().replace(0, np.nan),
        "close_ma_20": close / close.rolling(20).mean() - 1,
        "close_ma_60": close / close.rolling(60).mean() - 1,
        "daily_range": (frame["high"] - frame["low"]) / close,
    }, index=frame.index).replace([np.inf, -np.inf], np.nan)


def _direction_model(frame: pd.DataFrame, horizon: int) -> dict:
    """Predict P(close[t+h] > close[t]) using only then-available features.

    One purged chronological holdout is an initial diagnostic, not proof of
    robust calibration. Return no probability if fewer than 160 usable labels.
    """
    features = _features(frame)
    close = frame["close"].astype(float)
    target = (close.shift(-horizon) > close).astype(int)
    # Latest horizon rows have UNKNOWN labels, never include them.
    labeled = features.iloc[:-horizon].dropna()
    if len(labeled) < 160:
        return {"status": "insufficient_history", "probability_up": None,
                "message": "至少需要約 220 筆有效日線，才能訓練與留出驗證集。"}
    x = labeled.to_numpy(dtype=float)
    y = target.loc[labeled.index].to_numpy(dtype=int)
    latest = features.iloc[-1:]
    if latest.isna().any().any() or len(np.unique(y)) < 2:
        return {"status": "insufficient_variation", "probability_up": None}
    split = int(len(x) * 0.75)
    # Purge samples whose future label touches validation period.
    train_end = split - horizon
    if train_end < 90 or len(x) - split < 30 or len(np.unique(y[:train_end])) < 2:
        return {"status": "insufficient_holdout", "probability_up": None}

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, accuracy_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    def model():
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1500, C=0.3))

    m = model()
    m.fit(x[:train_end], y[:train_end])
    probs = m.predict_proba(x[split:])[:, 1]
    brier = float(brier_score_loss(y[split:], probs))
    baseline = float(np.mean(y[:train_end]))
    baseline_brier = float(brier_score_loss(y[split:],
                                          np.full(len(y) - split, baseline)))
    accuracy = float(accuracy_score(y[split:], probs >= 0.5))
    # Refit using only outcomes known as of most recent bar.
    m = model()
    m.fit(x, y)
    prediction = float(m.predict_proba(latest.to_numpy(dtype=float))[0, 1])
    return {
        "status": "validated_holdout" if brier < baseline_brier else "weak_vs_baseline",
        "probability_up": round(prediction, 4),
        "holdout_brier": round(brier, 4),
        "baseline_brier": round(baseline_brier, 4),
        "holdout_accuracy": round(accuracy, 4),
        "holdout_rows": int(len(y) - split),
        "training_rows": int(len(y)),
        "method": "regularized_logistic_regression_chronological_purged_holdout",
        "warning": "單次時間切分診斷；非經完整走勢外驗證校準的真實機率。",
    }


def _sample_paths(frame: pd.DataFrame, horizon: int, paths: int, seed: int) -> dict:
    close = frame["close"].to_numpy(dtype=float)
    lr = np.diff(np.log(close))
    if len(lr) < 100:
        raise ValueError("情境模擬至少需要 101 筆日線資料。")
    rng = np.random.default_rng(seed)
    block = min(5, horizon)
    momentum = pd.Series(close).pct_change(20).to_numpy()
    volatility = pd.Series(lr).rolling(20).std().to_numpy()
    current_vol = float(volatility[-1])
    current_momentum = float(momentum[-1])
    # Each candidate starts AFTER an observed market state; all data are historical.
    candidates = []
    for start in range(22, len(lr) - block + 1):
        state_idx = start - 1
        if not np.isfinite(volatility[state_idx]) or not np.isfinite(momentum[state_idx]):
            continue
        v = float(volatility[state_idx])
        if (0.5 * current_vol <= v <= 1.5 * current_vol and
                (momentum[state_idx] >= 0) == (current_momentum >= 0)):
            candidates.append(start)
    fallback = False
    if len(candidates) < 25:
        # Sparse regimes: a broad bootstrap is more honest than claiming regime matching.
        candidates = list(range(22, len(lr) - block + 1))
        fallback = True
    if not candidates:
        raise ValueError("可模擬的歷史區間不足。")

    ending = np.empty(paths, dtype=float)
    max_drawdown = np.empty(paths, dtype=float)
    samples = np.empty((paths, horizon), dtype=float)
    for p in range(paths):
        segments = []
        while len(segments) < horizon:
            idx = int(rng.choice(candidates))
            segments.extend(lr[idx:idx + block].tolist())
        future = close[-1] * np.exp(np.cumsum(segments[:horizon]))
        samples[p] = future
        ending[p] = float(future[-1])
        peaks = np.maximum.accumulate(np.r_[close[-1], future])[1:]
        max_drawdown[p] = float(np.min(future / peaks - 1))
    terminal_returns = ending / close[-1] - 1
    # Flat means finish between -2% and +2%; clear bins sum to 100%.
    upper = terminal_returns > 0.02
    lower = terminal_returns < -0.02
    def pct(x):
        return round(float(x), 4)
    checkpoints = sorted(set([1, min(5, horizon), min(10, horizon), horizon]))
    fan = [
        {"day": int(d), "p05": pct(np.quantile(samples[:, d - 1], 0.05)),
         "p25": pct(np.quantile(samples[:, d - 1], 0.25)),
         "p50": pct(np.quantile(samples[:, d - 1], 0.50)),
         "p75": pct(np.quantile(samples[:, d - 1], 0.75)),
         "p95": pct(np.quantile(samples[:, d - 1], 0.95))}
        for d in checkpoints
    ]
    return {
        "method": "regime_conditional_block_bootstrap",
        "calibrated": False,
        "paths": int(paths),
        "seed": int(seed),
        "regime_fallback": fallback,
        "candidate_blocks": len(candidates),
        "flat_band": "+/-2%",
        "scenario_frequency": {
            "up_over_2pct": pct(upper.mean()),
            "sideways_2pct": pct((~upper & ~lower).mean()),
            "down_below_minus_2pct": pct(lower.mean()),
        },
        "terminal_price_p05": pct(np.quantile(ending, 0.05)),
        "terminal_price_p50": pct(np.quantile(ending, 0.50)),
        "terminal_price_p95": pct(np.quantile(ending, 0.95)),
        "terminal_return_p05": pct(np.quantile(terminal_returns, 0.05)),
        "terminal_return_p50": pct(np.quantile(terminal_returns, 0.50)),
        "terminal_return_p95": pct(np.quantile(terminal_returns, 0.95)),
        "path_max_drawdown_p05": pct(np.quantile(max_drawdown, 0.05)),
        "fan": fan,
        "warning": "模擬比例不是經校準的未來發生機率；過去未發生的危機無法由抽樣保證涵蓋。",
    }


def predict_scenarios(frame: pd.DataFrame, symbol: str, source: str,
                      horizon: int = 20, paths: int = 2000, seed: int = 19) -> dict:
    if horizon not in (1, 5, 20, 60):
        raise ValueError("horizon 僅支援 1、5、20、60 個交易日。")
    if not (250 <= paths <= 5000):
        raise ValueError("paths 必須在 250～5000 之間。")
    if not (0 <= seed <= 2**32 - 1):
        raise ValueError("seed 超出範圍。")
    data = normalize_ohlcv(frame)
    if len(data) < max(120, horizon + 65):
        raise ValueError("有效日線不足，至少需要 120 筆且足以支援預測期間。")
    price = float(data["close"].iloc[-1])
    result = {
        "symbol": symbol,
        "source": source,
        "synthetic_data": source == "demo",
        "as_of": data["date"].iloc[-1].date().isoformat(),
        "observations": int(len(data)),
        "last_close": round(price, 4),
        "horizon_trading_days": horizon,
        "market_regime": {
            "momentum_20d": round(float(data["close"].iloc[-1] / data["close"].iloc[-21] - 1), 4),
            "realized_daily_volatility_20d": round(float(
                np.log(data["close"].astype(float)).diff().tail(20).std(ddof=1)), 4),
        },
        "simulation": _sample_paths(data, horizon, paths, seed),
        "ml_direction": _direction_model(data, horizon),
        "research_only": True,
        "disclaimer": "研究用途，並非投資建議；模擬與模型都不能保證未來結果。",
    }
    return result
