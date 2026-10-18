package ai.audible.companion

import android.os.Build
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

class CompanionApiClient(private var baseUrl: String = "http://192.168.0.107:8000/api/v1/companion") {

    private val fallbackUrl = "http://127.0.0.1:8000/api/v1/companion"
    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(4, TimeUnit.SECONDS)
        .writeTimeout(4, TimeUnit.SECONDS)
        .build()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    fun setBaseUrl(url: String) {
        baseUrl = if (url.endsWith("/")) url.removeSuffix("/") else url
    }

    private fun getCurrentIsoTimestamp(): String {
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        sdf.timeZone = java.util.TimeZone.getTimeZone("UTC")
        return sdf.format(Date())
    }

    private fun postJson(endpoint: String, json: JSONObject): Result<String> {
        val targets = listOf("$baseUrl$endpoint", "$fallbackUrl$endpoint")
        var lastException: Exception? = null

        for (targetUrl in targets) {
            try {
                val request = Request.Builder()
                    .url(targetUrl)
                    .post(json.toString().toRequestBody(jsonMediaType))
                    .build()

                client.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        return Result.success(response.body?.string() ?: "OK")
                    } else {
                        lastException = Exception("HTTP ${response.code} from $targetUrl: ${response.message}")
                    }
                }
            } catch (e: Exception) {
                lastException = e
            }
        }
        return Result.failure(lastException ?: IOException("Failed to connect to backend targets"))
    }

    suspend fun pairDevice(simOperator: String, batteryLevel: Int? = null): Result<String> = withContext(Dispatchers.IO) {
        val json = JSONObject().apply {
            put("device_id", Build.SERIAL.ifBlank { Build.MODEL })
            put("model", Build.MODEL)
            put("manufacturer", Build.MANUFACTURER)
            put("android_version", Build.VERSION.RELEASE)
            put("sdk_version", Build.VERSION.SDK_INT)
            put("sim_operator", simOperator)
            put("battery_level", batteryLevel ?: 100)
            put("paired_at", getCurrentIsoTimestamp())
        }
        postJson("/pair", json)
    }

    suspend fun reportCallEvent(state: String, incomingNumber: String?, callId: String? = null): Result<String> = withContext(Dispatchers.IO) {
        val json = JSONObject().apply {
            put("call_id", callId ?: System.currentTimeMillis().toString())
            put("state", state)
            put("incoming_number", incomingNumber ?: "Unknown")
            put("duration_seconds", 0)
            put("timestamp", getCurrentIsoTimestamp())
        }
        postJson("/call-event", json)
    }

    suspend fun reportAudioProbe(
        audioSourceTested: String,
        success: Boolean,
        decodableAudioCaptured: Boolean,
        pcmBytesReceived: Int,
        uplinkInjectable: Boolean,
        carrierAudioIsolated: Boolean,
        details: String
    ): Result<String> = withContext(Dispatchers.IO) {
        val json = JSONObject().apply {
            put("audio_source_tested", audioSourceTested)
            put("success", success)
            put("decodable_audio_captured", decodableAudioCaptured)
            put("pcm_bytes_received", pcmBytesReceived)
            put("uplink_injectable", uplinkInjectable)
            put("carrier_audio_isolated", carrierAudioIsolated)
            put("diagnostic_details", details)
        }
        postJson("/audio-probe", json)
    }

    suspend fun getPendingCommands(sessionId: String? = null): Result<List<JSONObject>> = withContext(Dispatchers.IO) {
        val query = if (!sessionId.isNullOrEmpty()) "?session_id=$sessionId" else ""
        val targets = listOf("$baseUrl/supermarket/pending-commands$query", "$fallbackUrl/supermarket/pending-commands$query")
        for (targetUrl in targets) {
            try {
                val request = Request.Builder().url(targetUrl).get().build()
                client.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        val bodyStr = response.body?.string() ?: "{}"
                        val json = JSONObject(bodyStr)
                        val cmdsJson = json.optJSONArray("commands")
                        val list = mutableListOf<JSONObject>()
                        if (cmdsJson != null) {
                            for (i in 0 until cmdsJson.length()) {
                                list.add(cmdsJson.getJSONObject(i))
                            }
                        }
                        return@withContext Result.success(list)
                    }
                }
            } catch (e: Exception) {
                // Try fallback
            }
        }
        Result.success(emptyList())
    }

    suspend fun triggerSpeakTest(): Result<String> = withContext(Dispatchers.IO) {
        val json = JSONObject()
        postJson("/supermarket/speak-test", json)
    }

    suspend fun sendCallerSpeech(speechText: String): Result<JSONObject> = withContext(Dispatchers.IO) {
        val json = JSONObject().apply {
            put("caller_speech", speechText)
        }
        val targets = listOf("$baseUrl/supermarket/chat", "$fallbackUrl/supermarket/chat")
        for (targetUrl in targets) {
            try {
                val request = Request.Builder()
                    .url(targetUrl)
                    .post(json.toString().toRequestBody(jsonMediaType))
                    .build()
                client.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        val bodyStr = response.body?.string() ?: "{}"
                        return@withContext Result.success(JSONObject(bodyStr))
                    }
                }
            } catch (e: Exception) {
                // Try fallback
            }
        }
        Result.failure(IOException("Failed to send caller speech"))
    }

    suspend fun reportAudioRoute(
        audioMode: String,
        speakerOn: Boolean,
        devName: String,
        voiceVol: Int,
        musicVol: Int
    ): Result<String> = withContext(Dispatchers.IO) {
        val json = JSONObject().apply {
            put("audio_mode", audioMode)
            put("speakerphone_on", speakerOn)
            put("communication_device", devName)
            put("stream_voice_call_volume", voiceVol)
            put("stream_music_volume", musicVol)
            put("sample_rate", 16000)
            put("timestamp", getCurrentIsoTimestamp())
        }
        postJson("/diagnostics/audio-route", json)
    }

    suspend fun ackCommand(commandId: String): Result<String> = withContext(Dispatchers.IO) {
        val json = JSONObject().apply {
            put("command_id", commandId)
            put("status", "COMPLETED")
        }
        postJson("/commands/ack", json)
    }

    suspend fun reportInboundSms(sender: String, message: String): Result<JSONObject> = withContext(Dispatchers.IO) {
        val json = JSONObject().apply {
            put("sender", sender)
            put("message", message)
            put("timestamp", getCurrentIsoTimestamp())
        }
        val targets = listOf("$baseUrl/sms/inbound", "$fallbackUrl/sms/inbound")
        for (targetUrl in targets) {
            try {
                val request = Request.Builder()
                    .url(targetUrl)
                    .post(json.toString().toRequestBody(jsonMediaType))
                    .build()
                client.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        val bodyStr = response.body?.string() ?: "{}"
                        return@withContext Result.success(JSONObject(bodyStr))
                    }
                }
            } catch (e: Exception) {
                // fallback
            }
        }
        Result.failure(IOException("Failed to report inbound SMS"))
    }

    suspend fun reportSmsSent(orderId: String, success: Boolean): Result<String> = withContext(Dispatchers.IO) {
        postJson("/sms/sent-callback?order_id=$orderId&success=$success", JSONObject())
    }
}
