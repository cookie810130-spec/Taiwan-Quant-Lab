package tw.quantlab.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.URL
import javax.net.ssl.HttpsURLConnection

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { QuantLabScreen() } }
    }
}

private fun apiCall(base: String, apiKey: String, path: String, payload: JSONObject? = null): JSONObject {
    require(base.startsWith("https://")) { "請輸入 Tailscale Serve 的 HTTPS 網址。" }
    require(apiKey.length >= 24) { "請填入 Windows 產生的 API Key。" }
    val conn = URL(base.trimEnd('/') + path).openConnection() as HttpsURLConnection
    conn.requestMethod = if (payload == null) "GET" else "POST"
    conn.connectTimeout = 15000
    conn.readTimeout = 180000
    conn.setRequestProperty("X-API-Key", apiKey)
    conn.setRequestProperty("Accept", "application/json")
    try {
        if (payload != null) {
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
        }
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
        if (code !in 200..299) {
            val detail = try { JSONObject(text).optString("detail", text) } catch (_: Exception) { text }
            error("HTTP ${code}: ${detail}")
        }
        return JSONObject(text)
    } finally {
        conn.disconnect()
    }
}

private fun percent(n: Double): String = "%.1f%%".format(java.util.Locale.US, n * 100.0)
private fun price(n: Double): String = "%.2f".format(java.util.Locale.US, n)

@Composable
fun QuantLabScreen() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("quantlab_v2_settings", 0) }
    var server by rememberSaveable { mutableStateOf(prefs.getString("url", "") ?: "") }
    // Secret stays in RAM; never persist or log it.
    var apiKey by remember { mutableStateOf("") }
    var symbol by rememberSaveable { mutableStateOf("2330") }
    var horizon by rememberSaveable { mutableIntStateOf(20) }
    var source by rememberSaveable { mutableStateOf("demo") }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("請填入 Tailscale HTTPS 網址及 API Key。") }
    var result by remember { mutableStateOf<JSONObject?>(null) }
    val scope = rememberCoroutineScope()

    fun run(path: String, payload: JSONObject? = null) {
        if (busy) return
        busy = true
        result = null
        scope.launch {
            try {
                val response = withContext(Dispatchers.IO) {
                    apiCall(server.trim(), apiKey, path, payload)
                }
                prefs.edit().putString("url", server.trim()).apply()
                if (payload == null) {
                    message = "Windows Python API 已連線；版本：${response.optString("version")}"
                } else {
                    result = response
                    message = "分析完成。以下是模型與模擬輸出，不是保證的未來機率。"
                }
            } catch (e: Exception) {
                message = "連線或計算失敗：${e.message ?: "未知錯誤"}"
            } finally {
                busy = false
            }
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text("台灣量子實驗室", style = MaterialTheme.typography.headlineSmall)
        Text("AI 情境推演 V2.0 · Windows Python 背景運算",
            style = MaterialTheme.typography.bodyMedium)
        OutlinedTextField(
            value = server, onValueChange = { server = it },
            label = { Text("Tailscale Serve HTTPS 網址") },
            placeholder = { Text("https://yourpc.tailnet.ts.net") },
            modifier = Modifier.fillMaxWidth(), singleLine = true
        )
        OutlinedTextField(
            value = apiKey, onValueChange = { apiKey = it },
            label = { Text("API Key（不會儲存）") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(), singleLine = true
        )
        Button(
            onClick = { run("/api/v2/info") }, enabled = !busy,
            modifier = Modifier.fillMaxWidth()
        ) { Text("測試 Windows 後端連線") }
        HorizontalDivider()
        Text("AI 未來情境模擬", style = MaterialTheme.typography.titleLarge)
        OutlinedTextField(
            value = symbol, onValueChange = { symbol = it.trim() },
            label = { Text("股票代號，例如 2330") },
            modifier = Modifier.fillMaxWidth(), singleLine = true
        )
        Text("資料來源")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("demo" to "測試", "db" to "本機資料庫", "finmind" to "FinMind").forEach {
                FilterChip(selected = source == it.first, onClick = { source = it.first },
                    label = { Text(it.second) })
            }
        }
        Text("預測期間（交易日）")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(1, 5, 20, 60).forEach {
                FilterChip(selected = horizon == it, onClick = { horizon = it },
                    label = { Text(it.toString()) })
            }
        }
        Button(
            onClick = {
                val req = JSONObject().put("symbol", symbol).put("source", source)
                    .put("horizon", horizon).put("paths", 1000).put("seed", 19)
                run("/api/v2/forecast", req)
            },
            enabled = !busy,
            modifier = Modifier.fillMaxWidth()
        ) { Text(if (busy) "分析中…" else "執行 AI 情境推演") }

        Text(message, color = MaterialTheme.colorScheme.secondary)
        result?.let { r ->
            val sim = r.getJSONObject("simulation")
            val scenarios = sim.getJSONObject("scenario_frequency")
            val ml = r.getJSONObject("ml_direction")
            HorizontalDivider()
            Text("${r.getString("symbol")} · ${r.getInt("horizon_trading_days")} 日",
                style = MaterialTheme.typography.titleLarge)
            if (r.optBoolean("synthetic_data")) {
                Text("⚠ 合成測試資料！不是真實股價或投資預測。",
                    color = MaterialTheme.colorScheme.error)
            } else {
                Text("資料日期：${r.optString("as_of")}；來源：${r.optString("source")}")
            }
            Text("最後收盤：${price(r.getDouble("last_close"))}")
            Text("歷史情境抽樣（非校準機率）", style = MaterialTheme.typography.titleMedium)
            Text("上漲超過 2%：${percent(scenarios.getDouble("up_over_2pct"))}")
            Text("盤整 ±2%：${percent(scenarios.getDouble("sideways_2pct"))}")
            Text("下跌超過 2%：${percent(scenarios.getDouble("down_below_minus_2pct"))}")
            Text("期末價格 P05 / P50 / P95：${price(sim.getDouble("terminal_price_p05"))} / " +
                    "${price(sim.getDouble("terminal_price_p50"))} / " +
                    price(sim.getDouble("terminal_price_p95")))
            Text("ML 方向模型", style = MaterialTheme.typography.titleMedium)
            if (!ml.isNull("probability_up")) {
                Text("估計上漲機率：${percent(ml.getDouble("probability_up"))}")
            } else {
                Text("資料不足，尚不能提供 ML 機率估計。")
            }
            Text("驗證：${ml.optString("status")}；${ml.optString("warning")}")
            Text("只供研究，不連接券商、不自動下單。")
        }
    }
}
