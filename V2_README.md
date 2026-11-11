# Taiwan-Quant-Lab V2.0-alpha — AI 未來情境實驗室

保留 V1 Streamlit。V2 在 Windows 背景執行 Python，Android 專用 APK 經 Tailscale HTTPS 操作。
**本版是可測試的研究原型，並非已驗證的投資預測產品。**

## 本版實作範圍
- Python FastAPI：API Key 驗證、健康檢查、行情來源、方向模型、路徑模擬、非持久化背景任務。
- ML：使用行情特徵的正則化 Logistic Regression，按時間順序切分並對訓練期和驗證期做 horizon purge，回報 Brier 與基準比較。若訓練/驗證不足便不輸出機率。
- Time Machine：依近 20 日動能與波動率匹配歷史區段，使用 5 日區塊 bootstrap，產生最多 5,000 條未來路徑、P05/P50/P95、±2% 情境頻率及最深回撤。
- DuckDB：使用者提供日線 CSV 可匯入，支援去重、查詢及來源標籤。
- Android Kotlin/Compose：設定 Tailscale HTTPS URL + API Key、查詢狀態、選股票/資料來源/期間、計算並顯示情境摘要。
- CI：GitHub Actions 執行 Python 測試、建置 Android Debug APK 與 Windows 來源 ZIP。

**尚未完成**：完整官方全市場歷史行情自動下載、完整市場狀態辨識、Chronos/TimesFM 大模型、GPT/Gemini 自動研究、預測機率的多期間校準驗證、永久任務佇列與正式商用簽章 APK。這些應在資料品質與原型實測通過後擴充。**不含券商實際下單功能。**

## Windows 安裝（與 V1 分開）

1. 下載分支原始碼或 Actions 的 Windows ZIP，解壓縮到 **C:\Taiwan-Quant-Lab-V2**。請不要覆蓋現有 **C:\Taiwan-Quant-Lab**。
2. 請先安裝 Python 3.12（已有則可沿用），雙擊 \`install_v2.bat\`；它會建立自己的 \`.venv-v2\`，不影響 V1 的 \`C:\Users\SOON\.venv\`。
3. 雙擊 \`start_v2_api.bat\`。API 在 \`http://127.0.0.1:8000\`，確認 \`http://127.0.0.1:8000/health\` 回應 \`status: ok\`。它只綁定本機回環介面。
4. 第一次啟動自動生成 API Key，位於 \`%LOCALAPPDATA%\TaiwanQuantLab\api_key.txt\`。使用記事本在 Windows 上開啟並複製到 Android APK；**不要上傳到 GitHub、雲端公開檔案或截圖**。
5. 如果檔案不見，程式可能生成新金鑰，Android 需更新。不要將 Key 寫進 BAT 或原始碼。

## Android APK 與 4G/5G 私人 HTTPS

1. 安裝並登入 Tailscale（Windows 與 Android 同一 tailnet）。不需要路由器開埠。
2. Windows CMD 執行（先確認 Tailscale 版本支援）：
   \`\`\`cmd
   tailscale serve --bg 8000
   tailscale serve status
   \`\`\`
   首次可能要求在管理頁啟用 HTTPS。輸出會提供類似 \`https://yourpc.yourtailnet.ts.net\` 的私有網址。**務必用 Serve，不是 Funnel**。
3. 到 GitHub Actions 分支 \`v2.0\` 的 \`V2 (Windows source + Android APK)\` 建置紀錄下載 \`taiwan-quant-lab-v2-android-debug-apk\`；解壓縮得到 \`app-debug.apk\`，傳到 Android 安裝（需允許該檔案管理器安裝未知來源）。
4. APK 輸入 Tailscale Serve HTTPS 網址及 API Key，按「測試 Windows 後端連線」，再按「執行 AI 情境推演」。
5. Android 必須保持 Tailscale VPN 連線；Windows 要開機、連網且背景 API 正常。APK 拒絕明文 HTTP 以保護金鑰。
6. 若 Android 顯示錯誤：先檢查 Windows 的 \`/health\`，再確認 \`tailscale serve status\`、APK 網址、API Key、手機 Tailscale VPN。

官方 Serve 說明：https://tailscale.com/docs/features/tailscale-serve

## 可選：Windows 登入後自動背景啟動

安裝完成後，使用 PowerShell 執行：
\`\`\`powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\windows\install_autostart.ps1"
Start-ScheduledTask -TaskName TaiwanQuantLabV2
\`\`\`
Windows 工作排程以目前登入者執行 \`pythonw.exe\`，不會開 CMD 黑窗；每次登入會啟動。日誌位於 \`%LOCALAPPDATA%\TaiwanQuantLab\server.log\`。解除設定執行 \`windows\uninstall_autostart.ps1\`。**需要登入 Windows 才會啟動，並非開機前即可運行的 Windows Service**。若要未登入也啟動，下一階段需另行設定 Windows Service 與專用服務帳號。

## 本機歷史日線資料匯入

CSV 標題必須是 \`date,open,high,low,close,volume\`，日期為 YYYY-MM-DD，按交易日逐筆，來源須自行確認。
在 V2 根資料夾開 CMD：
\`\`\`cmd
.venv-v2\Scripts\python.exe -m quantlab.v2.import_csv 2330 "C:\path\to\2330.csv"
\`\`\`
不重複儲存相同股票/日期。資料會放在 \`data/v2/quantlab.duckdb\`，來源標記 \`user_csv_unverified\`，**不宣稱一定是已校驗的 TWSE 官方行情**。APK 的資料來源選「本機資料庫」。原本 FinMind 仍可使用，但須在 Windows 設定 \`FINMIND_TOKEN\`，不把 Token 放進 APK。

## API 規格

- \`GET /health\`：本機與 tailnet 連線狀態，不需要 API Key。
- \`GET /api/v2/info\`：模型與資料源說明。
- \`GET /api/v2/data/symbols\`：本機 DuckDB 股票清單。
- \`POST /api/v2/forecast\`：同步計算。
- \`POST /api/v2/jobs/forecast\`、\`GET /api/v2/jobs/{id}\`：簡易背景任務；重啟後會清除。
- 除健康檢查外，請求須含 \`X-API-Key\`。

範例請求 body：
\`\`\`json
{"symbol":"2330","source":"demo","horizon":20,"paths":1000,"seed":19}
\`\`\`
可選資料源：\`demo\`、\`db\`、\`finmind\`。demo 是合成測試資料，**不可用來決定投資**。

## 方法限制

- 10,000 次模擬不等於 10,000 份獨立證據。相似波動率、趨勢的區塊重抽樣不會預知黑天鵝、重大事件或市場結構改變。
- ML 的機率來自一次留出時間切分，Brier score 僅是初步品質診斷。若 \`weak_vs_baseline\`，表示它在留出資料上的 Brier 分數甚至不及簡單基準，**不應把模型數字當可靠機率**。
- 沒有完整 Walk-forward、真正無洩漏的企業事件時間戳與分市場校準之前，不提供交易建議。
- MIT License 的外部 day-trader-skill 供設計參考，本版情境模擬是獨立實作，未複製它的核心程式碼。
