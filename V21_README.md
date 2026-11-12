# Taiwan-Quant-Lab V2.1-alpha — 真實資料更新與預測驗證

本分支從 v2.0 分出，main/V1 與 v2.0 原始碼沒有被覆寫。保留 Python FastAPI + Tailscale Serve + Android 架構。

## 本版新增
- TWSE 官方 STOCK_DAY 月報日線：四位數上市股票，無須 Token，首次最多回補四年，之後每次只重抓最近 45 日，跨月更新；台灣時間 17:00 前不匯入當天日期。
- DuckDB 官方來源標記 twse_official，使用者 CSV 仍標記 user_csv_unverified。未經調整原始股價不能直接當成含息報酬。
- 每日真實 AI 預測快照：1/5/20/60 個交易日，含當時的模型估計、模擬價格區間、資料日期、模型版本；同一股票、同一基準日期、同一期限、同一模型版，只保留第一筆（不可事後覆寫）。
- 到期驗證：只有資料庫取得預測日後第 N 個實際交易日的收盤價，才會更新驗證結果；支援 Brier、方向命中率與模擬區間覆蓋率。沒有歷史預測時不編造準確率。
- Android 新增真實行情更新、一鍵更新＋AI 預測＋保存、查詢預測到期評分。
- 可選 Windows 每週一至週五 17:30 台灣時間自動更新觀察清單並保存預測。

## 限制
本版無憑證官方更新限於證交所上市四位數股票，不包含 TPEx 上櫃、興櫃、全市場單鍵匯入、除權息還原資料。尚未整合 GPT/Gemini 自主研究、Chronos/TimesFM 或可驗證的完整市場機率校準。原有 FinMind 資料選項仍保留在 V2 的既有 API。沒有券商委託與自動下單。本版是研究 Alpha，非投資建議。

TWSE 官方月資料：https://www.twse.com.tw/exchangeReport/STOCK_DAY

## Windows 安裝（另建資料夾，不覆蓋 V2.0）
1. 從 GitHub Actions v2.1 成功建置中下載 Windows source Artifact ZIP，解壓內部的 Windows ZIP 到 C:\Taiwan-Quant-Lab-V2.1。
2. 雙擊 install_v2.bat，建立本目錄自己的 .venv-v2 環境；不要覆蓋 C:\Taiwan-Quant-Lab-V2。
3. 先在舊 V2.0 API 的 CMD 窗口按 Ctrl+C 釋出 8000，然後啟動新目錄的 start_v2_api.bat。
4. Windows Chrome 開啟 http://127.0.0.1:8000/health 應看到 version: v2.1-alpha。
5. 原 Tailscale Serve 代理 127.0.0.1:8000 通常不用變更。檢查：tailscale serve status。若 Serve 關閉，再執行：tailscale serve --bg 8000。**不要啟用 Funnel 或開放路由器 8000 埠。**
6. Android 請使用 Python 當次顯示的 API Key。使用 Microsoft Store Python 3.12 時，Key 可能位於：
   C:\Users\SOON\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\Local\TaiwanQuantLab\api_key.txt
   可用 where /r C:\Users api_key.txt 搜尋。請勿將金鑰發到聊天或 GitHub。

## Android
- 同一次 GitHub Actions 下載 taiwan-quant-lab-v2.1-android-debug-apk Artifact，解壓安裝 app-debug.apk。
- V2.1 使用獨立 Android applicationId，可以與 V2.0 並存。
- 輸入 Tailscale Serve HTTPS 地址和 API Key，先測試 Windows 連線。
- 以股票 2330 為例，按「更新行情＋AI 預測＋永久紀錄」，首次下載四年資料需連續查詢約 48 個月份，可能需數十秒。
- 按「查看到期預測驗證報告」，第一次顯示 0 筆已驗證很正常。因為必須真正經過未來交易日，不可以把歷史回測當成以前發出的預測。

## 每日 17:30 Windows 自動更新

Windows 的時區須設定為 Taipei Standard Time。開 PowerShell，進到 C:\Taiwan-Quant-Lab-V2.1，執行：

    powershell -NoProfile -ExecutionPolicy Bypass -File ".\windows\install_v21_daily_task.ps1"

Windows 工作排程器會建立 TaiwanQuantLabV21Daily，週一至週五 17:30 執行，適用登入中的 Windows 使用者。它不是未登入也能運作的 Windows Service。電腦關機、睡眠或離線時無法準時更新。

手動執行以確認：

    .venv-v2\Scripts\python.exe -m quantlab.v2.daily --symbols 2330 --horizons 1,5,20 --paths 500

預設只追蹤 2330。可自行建立 data\v2\watchlist.json，例如內容如下：

    ["2330","2317","2454"]

最多 30 檔，以避免對 TWSE 發出大量請求。更新紀錄：data\v2\daily.log。
移除排程：

    powershell -NoProfile -ExecutionPolicy Bypass -File ".\windows\uninstall_v21_daily_task.ps1"

## API（除 /health 外須 X-API-Key）
- POST /api/v2.1/data/update: {"symbol":"2330","years":4}
- POST /api/v2.1/research: {"symbol":"2330","source":"db","years":4,"horizon":20,"paths":1000,"seed":19}，完成更新、研究與存檔。
- POST /api/v2.1/forecast: 使用已有的真實本機行情產生預測與存檔，不重新下載。
- GET /api/v2.1/history?symbol=2330&limit=30
- GET /api/v2.1/scorecard
- GET /api/v2.1/status
- 既有 /api/v2/forecast 與 /api/v2/info 保持相容。

## 方法限制
情境模擬分布不是經完整校準的真實未來發生機率。請觀察樣本數與 Brier 分數；模型可能不及簡單基準。未來資料不足時維持 pending。日線使用官方未還原行情，除權息事件可能導致價格變化與總報酬不一致。當 Windows Task 與 Android 同時寫入 DuckDB 時，跨進程檔案鎖可能導致一方失敗，請避免同步執行。
