from datetime import date, timedelta
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from quantlab.data.sample import make_sample_data
from quantlab.data.finmind import fetch_finmind_prices, FinMindError
from quantlab.indicators import add_indicators
from quantlab.strategy import generate_signals
from quantlab.backtest import run_backtest
from quantlab.config import DEFAULTS

st.set_page_config(page_title="Taiwan Quant Lab", page_icon="📈", layout="wide")
st.title("📈 Taiwan Quant Lab")
st.caption("台股量化研究平台 · V1.0 · 預設使用合成測試資料，不會送出真實委託")

with st.sidebar:
    st.header("資料與策略設定")
    source = st.radio("行情來源", ["內建測試資料", "FinMind 台股日線 API"], index=0)
    symbol = st.text_input("股票代號", value="2330", help="FinMind 模式請輸入台股代號，例如 2330")
    end_date = st.date_input("資料結束日", value=date.today())
    start_date = st.date_input("資料開始日", value=end_date - timedelta(days=365 * 3))
    st.divider()
    st.subheader("策略參數")
    fast_ma = st.number_input("短期均線", min_value=2, max_value=100, value=20)
    slow_ma = st.number_input("長期均線", min_value=5, max_value=250, value=60)
    rsi_min = st.slider("RSI 下限", min_value=10, max_value=60, value=40)
    rsi_max = st.slider("RSI 上限", min_value=40, max_value=90, value=70)
    initial_cash = st.number_input("模擬本金（新台幣）", min_value=10000, max_value=100000000, value=1000000, step=100000)
    fee_rate = st.number_input("單邊手續費率", min_value=0.0, max_value=0.02, value=0.001425, step=0.0001, format="%.5f")
    tax_rate = st.number_input("賣出證交稅率", min_value=0.0, max_value=0.02, value=0.003, step=0.0005, format="%.4f")
    slippage = st.number_input("單邊滑價率", min_value=0.0, max_value=0.02, value=0.001, step=0.0005, format="%.4f")
    st.caption("費率為可調整的示範假設，請依券商、交易類型與當期規定確認。")

if start_date >= end_date:
    st.error("開始日期必須早於結束日期。")
    st.stop()
if fast_ma >= slow_ma:
    st.error("短期均線必須小於長期均線。")
    st.stop()
if rsi_min >= rsi_max:
    st.error("RSI 下限必須小於上限。")
    st.stop()

try:
    if source == "內建測試資料":
        raw = make_sample_data(start_date, end_date, symbol=symbol or "2330")
        st.info("目前使用可重現的合成行情，並非真實台股歷史價格。")
    else:
        token = os.getenv("FINMIND_TOKEN", "").strip()
        if not token:
            st.warning("尚未設定 FINMIND_TOKEN。請在部署平台的 Secrets 或本機環境變數設定，或先切回內建測試資料。")
            st.stop()
        raw = fetch_finmind_prices(symbol.strip(), start_date.isoformat(), end_date.isoformat(), token)
except FinMindError as exc:
    st.error(f"取得行情失敗：{exc}")
    st.stop()
except Exception as exc:
    st.error(f"載入資料時發生錯誤：{exc}")
    st.stop()

if raw.empty or len(raw) < max(slow_ma + 5, 70):
    st.error("資料筆數不足以計算目前的均線。請延長日期區間或確認股票代號。")
    st.stop()

params = {"fast_ma": int(fast_ma), "slow_ma": int(slow_ma), "rsi_min": int(rsi_min), "rsi_max": int(rsi_max)}
data = add_indicators(raw, fast_ma=fast_ma, slow_ma=slow_ma)
data = generate_signals(data, rsi_min=rsi_min, rsi_max=rsi_max)
result = run_backtest(data, initial_cash=float(initial_cash), fee_rate=float(fee_rate), tax_rate=float(tax_rate), slippage=float(slippage))

latest = data.iloc[-1]
m1, m2, m3, m4 = st.columns(4)
m1.metric("最新收盤價", f"${latest['close']:,.2f}")
m2.metric("策略總報酬", f"{result.metrics['total_return']:.2%}")
m3.metric("買入持有報酬", f"{result.metrics['buy_hold_return']:.2%}")
m4.metric("最大回撤", f"{result.metrics['max_drawdown']:.2%}")

tab1, tab2, tab3, tab4 = st.tabs(["行情與指標", "回測績效", "交易紀錄", "方法與限制"])
with tab1:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=data["date"], open=data["open"], high=data["high"], low=data["low"], close=data["close"], name="K線"))
    fig.add_trace(go.Scatter(x=data["date"], y=data["ma_fast"], name=f"MA{fast_ma}", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=data["date"], y=data["ma_slow"], name=f"MA{slow_ma}", line=dict(width=1.5)))
    fig.update_layout(height=560, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)
    sub = go.Figure()
    sub.add_trace(go.Scatter(x=data["date"], y=data["rsi"], name="RSI"))
    sub.add_hline(y=rsi_min, line_dash="dash")
    sub.add_hline(y=rsi_max, line_dash="dash")
    sub.update_layout(height=250, yaxis_range=[0, 100], margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(sub, use_container_width=True)
    macd_fig = go.Figure()
    macd_fig.add_trace(go.Scatter(x=data["date"], y=data["macd"], name="MACD"))
    macd_fig.add_trace(go.Scatter(x=data["date"], y=data["macd_signal"], name="Signal"))
    macd_fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(macd_fig, use_container_width=True)

with tab2:
    st.subheader("資金曲線")
    equity_fig = go.Figure()
    equity_fig.add_trace(go.Scatter(x=result.equity_curve["date"], y=result.equity_curve["strategy_equity"], name="策略資產"))
    equity_fig.add_trace(go.Scatter(x=result.equity_curve["date"], y=result.equity_curve["buy_hold_equity"], name="買入持有基準"))
    equity_fig.update_layout(height=380, yaxis_title="資產（TWD）", margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(equity_fig, use_container_width=True)
    metrics = result.metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("交易筆數", str(metrics["trade_count"]))
    c2.metric("勝率", f"{metrics['win_rate']:.1%}")
    c3.metric("Sharpe（年化估計）", f"{metrics['sharpe']:.2f}")
    c4.metric("期末資產", f"${metrics['final_equity']:,.0f}")
    st.dataframe(pd.DataFrame([{"指標": k, "數值": v} for k, v in metrics.items()]), use_container_width=True, hide_index=True)

with tab3:
    if result.trades.empty:
        st.info("這段期間沒有完成的交易。可嘗試延長日期或調整參數。")
    else:
        st.dataframe(result.trades, use_container_width=True, hide_index=True)
        st.download_button("下載交易紀錄 CSV", result.trades.to_csv(index=False).encode("utf-8-sig"), file_name=f"{symbol}_trades.csv", mime="text/csv")

with tab4:
    st.markdown("""
**策略規則（長倉、日線、研究用途）**
- 進場訊號：短期均線高於長期均線、RSI 位於設定區間，且 MACD 高於訊號線。
- 出場訊號：短期均線低於長期均線，或 MACD 低於訊號線，或 RSI 低於下限。
- 訊號在當日收盤後計算，最早於下一交易日開盤模擬成交，避免同日收盤價前視偏差。
- 預設全倉/空倉示範，僅支援整股以外的簡化股數計算；實際台股交易單位與零股規則尚未完整建模。
- 回測結果不代表未來績效。尚未涵蓋停牌、漲跌停無法成交、除權息完整調整、流動性及所有券商規則。
- FinMind 來源需設定 `FINMIND_TOKEN`，並自行確認資料使用條款與 API 額度。
""")
    st.json({"strategy_parameters": params, "data_source": source, "symbol": symbol})
st.caption("Taiwan Quant Lab V1.0 · 研究與模擬用途；目前不會連接券商或送出真實訂單。")
