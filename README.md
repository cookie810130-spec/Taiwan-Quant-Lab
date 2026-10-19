# Taiwan Quant Lab

台股量化研究平台 V1.0：內建合成測試資料、技術指標、均線＋RSI＋MACD 策略、日線回測與交易紀錄。

> **重要：** 預設行情是合成測試資料，不是真實台股行情。本專案僅供研究與模擬，不連接券商、不會送出真實委託，也不保證獲利。

## 功能

- Streamlit 網頁介面，手機/桌面瀏覽器可用
- K 線、MA、RSI、MACD 圖表
- 均線趨勢＋RSI 區間＋MACD 訊號策略
- 收盤後產生訊號，下一交易日開盤模擬執行
- 自訂虛擬本金、手續費、證交稅與滑價
- 資金曲線、買入持有基準、最大回撤、Sharpe、勝率與交易紀錄
- 可選擇 FinMind API 取得台股日線資料
- pytest 自動測試與 GitHub Actions

## 專案結構

```text
Taiwan-Quant-Lab/
├── app.py
├── quantlab/
│   ├── config.py
│   ├── indicators.py
│   ├── strategy.py
│   ├── backtest.py
│   └── data/
│       ├── sample.py
│       └── finmind.py
├── tests/
│   ├── test_indicators.py
│   └── test_strategy_backtest.py
├── .github/workflows/tests.yml
├── .env.example
├── requirements.txt
├── runtime.txt
├── Procfile
└── README.md
```

## 本機執行

建議使用 Python 3.12。

### 1. 解壓縮後進入專案資料夾

```bash
cd Taiwan-Quant-Lab
```

### 2. 建立虛擬環境並安裝套件

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS / Linux：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 啟動網頁

```bash
streamlit run app.py
```

終端機會顯示本機網址，通常是 `http://localhost:8501`。

### 4. 執行測試

```bash
pytest -q
```

## 部署到 Streamlit Community Cloud

1. 在 GitHub 建立新的 **Public repository**，名稱可用 `Taiwan-Quant-Lab`。
2. 將 ZIP 解壓縮，將專案內所有檔案與資料夾上傳到 repository 根目錄（不是把 ZIP 原檔當成程式）。
3. 確認 `app.py`、`requirements.txt`、`quantlab/` 位於 repository 根目錄。
4. 開啟 [Streamlit Community Cloud](https://share.streamlit.io/) 並連結 GitHub。
5. 建立新 App，選擇 repository、分支與主程式 `app.py`。
6. 部署後先選「內建測試資料」，確認圖表、回測與交易紀錄可用。
7. 若需使用 FinMind 真實資料，在 App 的 **Settings / Secrets** 設定：
   ```toml
   FINMIND_TOKEN = "你的 FinMind Token"
   ```
8. 重新啟動 App，再切換資料來源為「FinMind 台股日線 API」。

Streamlit Cloud 的可用額度、休眠、版本支援與部署流程可能調整，請以官方文件為準。也可以部署到其他支援 Python 常駐服務的平台。

## FinMind 真實行情

- 註冊與取得 Token：<https://finmindtrade.com/>
- API 文件：<https://finmind.github.io/>
- 本專案使用 `TaiwanStockPrice` 資料集與 API v4。
- 免費額度、更新頻率、商用用途、資料展示及再散布權利，請依當期官方條款確認。
- `.env.example` 只是環境變數範本。程式不會自動讀取 `.env` 檔；本機可在 shell 設定 `FINMIND_TOKEN`，或自行安裝 `python-dotenv` 並設定載入。雲端建議使用平台 Secrets。
- **不要將真實 Token 提交到 GitHub、截圖或公開日誌。**

## 策略定義

進場（於訊號後一個交易日開盤模擬）：
- MA 快線 > MA 慢線
- RSI 在使用者設定的區間內
- MACD > MACD Signal

出場（於訊號後一個交易日開盤模擬）：
- MA 快線 < MA 慢線，或
- MACD < MACD Signal，或
- RSI < RSI 下限

本版採長倉、全倉/空倉簡化模型。指標只使用當日及過去資料，訊號不在同一根 K 線成交。尚未完整模擬台股整股/零股、漲跌停、停牌、除權息調整、流動性、部分成交及券商實際費率等情境。

## 風險與後續工作

- 回測會受資料品質、交易成本與假設影響；過去績效不代表未來結果。
- 目前的策略不是投資建議，也未通過實盤驗證。
- 上線自動下單前，需要另外開發券商 API Adapter、交易前風控、冪等訂單、異常告警、密鑰管理、人工停機開關與模擬/實盤隔離，並遵守券商及相關法規。
- 建議下一階段加入：除權息/還原股價處理、台股交易單位、Walk-forward 樣本外驗證、更多策略及資料來源抽象介面。

## 授權

本專案程式碼以 MIT License 提供；第三方套件與金融資料各自適用其原始授權及服務條款。FinMind 資料不因本專案採 MIT 授權而自動取得再散布或商用授權。
