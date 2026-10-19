from dataclasses import dataclass
import math
import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict


def run_backtest(frame: pd.DataFrame, initial_cash: float = 1_000_000.0,
                 fee_rate: float = 0.001425, tax_rate: float = 0.003,
                 slippage: float = 0.001) -> BacktestResult:
    """Long-only daily backtest. Signals at close execute at next day's open."""
    if initial_cash <= 0:
        raise ValueError("initial_cash 必須大於 0。")
    if min(fee_rate, tax_rate, slippage) < 0:
        raise ValueError("交易成本不可為負數。")
    data = frame.reset_index(drop=True).copy()
    if data.empty:
        raise ValueError("回測資料不可為空。")
    cash = float(initial_cash)
    shares = 0
    entry_price = None
    entry_date = None
    trades = []
    curve = []
    for i, row in data.iterrows():
        # Execute yesterday's signal at today's open, adjusted for assumed slippage.
        if i > 0:
            prior = data.iloc[i - 1]
            if shares == 0 and bool(prior.get("entry_signal", False)):
                execution = float(row["open"]) * (1 + slippage)
                # Whole-share simplified sizing; Taiwan board-lot constraints are not modeled.
                qty = int(cash / (execution * (1 + fee_rate)))
                if qty > 0:
                    cost = qty * execution
                    fee = cost * fee_rate
                    if cost + fee <= cash:
                        cash -= cost + fee
                        shares = qty
                        entry_price = execution
                        entry_date = row["date"]
            elif shares > 0 and bool(prior.get("exit_signal", False)):
                execution = float(row["open"]) * (1 - slippage)
                proceeds = shares * execution
                fee = proceeds * fee_rate
                tax = proceeds * tax_rate
                cash += proceeds - fee - tax
                pnl = cash - initial_cash if not trades else (proceeds - fee - tax) - (shares * entry_price)
                trades.append({
                    "entry_date": pd.Timestamp(entry_date).date().isoformat(),
                    "exit_date": pd.Timestamp(row["date"]).date().isoformat(),
                    "shares": shares,
                    "entry_price": round(float(entry_price), 4),
                    "exit_price": round(float(execution), 4),
                    "net_exit_proceeds": round(float(proceeds - fee - tax), 2),
                    "trade_return_pct": round(((execution * (1 - fee_rate - tax_rate)) / (entry_price * (1 + fee_rate)) - 1) * 100, 3),
                    "note": "成本與滑價為模擬估計",
                })
                shares = 0
                entry_price = None
                entry_date = None
        close_value = shares * float(row["close"])
        curve.append({"date": row["date"], "strategy_equity": cash + close_value})
    equity = pd.DataFrame(curve)
    equity["buy_hold_equity"] = initial_cash * (data["close"] / float(data["close"].iloc[0]))
    daily_returns = equity["strategy_equity"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    peak = equity["strategy_equity"].cummax()
    drawdown = equity["strategy_equity"] / peak - 1
    final_equity = float(equity["strategy_equity"].iloc[-1])
    total_return = final_equity / initial_cash - 1
    buy_hold_return = float(equity["buy_hold_equity"].iloc[-1] / initial_cash - 1)
    std = float(daily_returns.std(ddof=1)) if len(daily_returns) > 1 else 0.0
    sharpe = (float(daily_returns.mean()) / std * math.sqrt(252)) if std > 0 else 0.0
    trade_df = pd.DataFrame(trades)
    win_rate = float((trade_df["trade_return_pct"] > 0).mean()) if not trade_df.empty else 0.0
    metrics = {
        "total_return": total_return,
        "buy_hold_return": buy_hold_return,
        "max_drawdown": float(drawdown.min()),
        "sharpe": sharpe,
        "trade_count": int(len(trade_df)),
        "win_rate": win_rate,
        "final_equity": final_equity,
        "initial_cash": float(initial_cash),
    }
    return BacktestResult(equity_curve=equity, trades=trade_df, metrics=metrics)
