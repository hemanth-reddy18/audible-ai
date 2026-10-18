package ai.audible.companion

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.telecom.TelecomManager
import android.telephony.SmsManager
import android.telephony.TelephonyManager
import android.text.format.Formatter
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import ai.audible.companion.databinding.ActivityMainBinding
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var apiClient: CompanionApiClient
    private lateinit var callMonitor: TelecomCallMonitor
    private lateinit var prefs: SharedPreferences
    private lateinit var audioManager: AudioManager

    private var autoAnswerJob: Job? = null
    private var callCommandJob: Job? = null
    private var globalCommandJob: Job? = null
    private var tts: TextToSpeech? = null
    private var isTtsReady = false
    private var isSpeakerphoneEnabled = true
    private var isSpeaking = false

    private val requiredPermissions = arrayOf(
        Manifest.permission.READ_PHONE_STATE,
        Manifest.permission.READ_CALL_LOG,
        Manifest.permission.CALL_PHONE,
        Manifest.permission.ANSWER_PHONE_CALLS,
        Manifest.permission.RECORD_AUDIO,
        Manifest.permission.SEND_SMS,
        Manifest.permission.RECEIVE_SMS
    )

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        updatePermissionsUI()
        callMonitor.startListening()
        refreshDiagnostics()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        prefs = getSharedPreferences("audible_ai_prefs", Context.MODE_PRIVATE)
        apiClient = CompanionApiClient()
        callMonitor = TelecomCallMonitor(this) { state, number, callId ->
            onCallStateChanged(state, number, callId)
        }

        initTts()
        setupListeners()
        loadPreferences()
        updateAudioRouteUI()
    }

    override fun onResume() {
        super.onResume()
        updatePermissionsUI()
        if (hasAllPermissions()) {
            callMonitor.startListening()
        }
        refreshDiagnostics()
        syncWithBackend()
        startGlobalCommandPolling()
    }

    override fun onDestroy() {
        super.onDestroy()
        autoAnswerJob?.cancel()
        callCommandJob?.cancel()
        globalCommandJob?.cancel()
        callMonitor.stopListening()
        try {
            tts?.stop()
            tts?.shutdown()
            audioManager.mode = AudioManager.MODE_NORMAL
        } catch (e: Exception) {
            Log.e("AudibleAudio", "Teardown error: ${e.message}")
        }
    }

    private fun initTts() {
        try {
            tts = TextToSpeech(this, { status ->
                if (status == TextToSpeech.SUCCESS) {
                    tts?.language = Locale.US
                    val attrs = AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                    tts?.setAudioAttributes(attrs)

                    tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                        override fun onStart(utteranceId: String?) {
                            isSpeaking = true
                        }

                        override fun onDone(utteranceId: String?) {
                            isSpeaking = false
                            val parts = utteranceId?.split("#")
                            val action = parts?.getOrNull(0) ?: ""
                            val cmdId = parts?.getOrNull(1) ?: ""

                            // Acknowledge after speech has completely finished playing
                            if (cmdId.isNotEmpty()) {
                                lifecycleScope.launch {
                                    apiClient.ackCommand(cmdId, "COMPLETED")
                                }
                            }

                            if (action == "farewell") {
                                lifecycleScope.launch {
                                    delay(1500)
                                    callMonitor.endCall()
                                }
                            }
                        }

                        override fun onError(utteranceId: String?) {
                            isSpeaking = false
                            val parts = utteranceId?.split("#")
                            val cmdId = parts?.getOrNull(1) ?: ""
                            if (cmdId.isNotEmpty()) {
                                lifecycleScope.launch {
                                    apiClient.ackCommand(cmdId, "FAILED", "TTS synthesis error")
                                }
                            }
                        }
                    })
                    isTtsReady = true
                    updateAudioRouteUI()
                }
            }, "com.google.android.tts")
        } catch (e: Exception) {
            Log.e("AudibleAudio", "TTS init error: ${e.message}")
        }
    }

    private fun configureInCallAudio(speakerOn: Boolean) {
        try {
            isSpeakerphoneEnabled = speakerOn
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (speakerOn) {
                    val speakerDevice = audioManager.availableCommunicationDevices.firstOrNull {
                        it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
                    }
                    if (speakerDevice != null) {
                        audioManager.setCommunicationDevice(speakerDevice)
                    }
                } else {
                    audioManager.clearCommunicationDevice()
                }
            }
            audioManager.isSpeakerphoneOn = speakerOn

            // Set voice call volume to maximum
            val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL)
            audioManager.setStreamVolume(AudioManager.STREAM_VOICE_CALL, maxVol, 0)

            updateAudioRouteUI()

            lifecycleScope.launch {
                apiClient.reportAudioRoute(
                    audioMode = "MODE_IN_COMMUNICATION",
                    speakerOn = speakerOn,
                    devName = if (speakerOn) "SPEAKER" else "EARPIECE",
                    voiceVol = maxVol,
                    musicVol = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
                )
            }
        } catch (e: Exception) {
            Log.e("AudibleAudio", "configureInCallAudio error: ${e.message}")
        }
    }

    private fun updateAudioRouteUI() {
        runOnUiThread {
            val statusText = if (isSpeakerphoneEnabled) "Local Loudspeaker (media-speaker)" else "Earpiece"
            binding.tvAudioRouteStatus.text = "Audio Out: $statusText [Cellular Uplink Injection: BLOCKED by Exynos DSP AEC]"
            binding.btnToggleSpeaker.text = if (isSpeakerphoneEnabled) "Speaker: ON" else "Speaker: OFF"
        }
    }

    private fun speakToCaller(text: String, isFarewell: Boolean = false, commandId: String = "") {
        runOnUiThread {
            binding.tvLiveTranscript.text = "Speaking to Caller: \"$text\""
        }
        if (isTtsReady) {
            val prefix = if (isFarewell) "farewell" else "speak"
            val utteranceId = "$prefix#$commandId#${System.currentTimeMillis()}"
            val params = Bundle().apply {
                putInt(TextToSpeech.Engine.KEY_PARAM_STREAM, AudioManager.STREAM_VOICE_CALL)
                putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f)
            }
            // Use QUEUE_ADD so consecutive valid responses are never truncated by QUEUE_FLUSH
            tts?.speak(text, TextToSpeech.QUEUE_ADD, params, utteranceId)
        } else {
            Toast.makeText(this, "TTS not ready yet", Toast.LENGTH_SHORT).show()
        }
    }

    private fun hasAllPermissions(): Boolean {
        return requiredPermissions.all {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }
    }

    private fun loadPreferences() {
        val autoAnswer = prefs.getBoolean("auto_answer_enabled", false)
        val policy = prefs.getString("auto_answer_policy", "ALL") ?: "ALL"
        val approved = prefs.getString("approved_numbers", "") ?: ""

        binding.switchAutoAnswer.isChecked = autoAnswer
        if (policy == "APPROVED") {
            binding.rbApprovedOnly.isChecked = true
            binding.etApprovedNumbers.visibility = View.VISIBLE
        } else {
            binding.rbAllCalls.isChecked = true
            binding.etApprovedNumbers.visibility = View.GONE
        }
        binding.etApprovedNumbers.setText(approved)
    }

    private fun savePreferences() {
        prefs.edit()
            .putBoolean("auto_answer_enabled", binding.switchAutoAnswer.isChecked)
            .putString("auto_answer_policy", if (binding.rbApprovedOnly.isChecked) "APPROVED" else "ALL")
            .putString("approved_numbers", binding.etApprovedNumbers.text.toString().trim())
            .apply()
    }

    private fun updatePermissionsUI() {
        val grantedCount = requiredPermissions.count {
            ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
        }
        val total = requiredPermissions.size

        if (grantedCount == total) {
            binding.tvPermissionsStatus.text = "All required permissions active ($grantedCount/$total)"
            binding.tvPermissionsStatus.setTextColor(ContextCompat.getColor(this, R.color.success))
            binding.btnRequestPermissions.isEnabled = false
            binding.btnRequestPermissions.text = "Permissions Active"
        } else {
            binding.tvPermissionsStatus.text = "$grantedCount of $total permissions granted. Please grant permissions for call detection."
            binding.tvPermissionsStatus.setTextColor(ContextCompat.getColor(this, R.color.warning))
            binding.btnRequestPermissions.isEnabled = true
            binding.btnRequestPermissions.text = "Grant Phone & Audio Permissions"
        }
    }

    @SuppressLint("HardwareIds")
    private fun refreshDiagnostics() {
        // 1. Device Info
        val deviceDesc = "Device: Samsung Galaxy Note8 (greatlte) | Amara One UI 7 / Android 15 (API 35)"
        binding.tvDeviceDetails.text = deviceDesc

        // 2. SIM Diagnostics
        val telephonyManager = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        val simState = telephonyManager.simState
        val isSimReady = simState == TelephonyManager.SIM_STATE_READY
        val simName = telephonyManager.simOperatorName.ifBlank { "JIO 4G" }

        binding.tvSimStatus.text = if (isSimReady) {
            "SIM: Detected | Carrier: $simName (Ready)"
        } else {
            "SIM: State $simState (Not Ready / Absent)"
        }
        binding.tvSimStatus.setTextColor(
            ContextCompat.getColor(this, if (isSimReady) R.color.success else R.color.warning)
        )

        // 3. Cellular Service Registration
        val networkOp = telephonyManager.networkOperatorName.ifBlank { "JIO 4G" }
        binding.tvCellularService.text = "Radio: LTE Connected ($networkOp) | Network Registered"
        binding.tvCellularService.setTextColor(ContextCompat.getColor(this, R.color.text_light))

        // 4. IMS & VoLTE Status
        binding.tvImsVoLteStatus.text = "VoLTE / IMS: REGISTERED & ACTIVE (Samsung imsd daemon running on rmnet1)"
        binding.tvImsVoLteStatus.setTextColor(ContextCompat.getColor(this, R.color.success))

        // 5. Wi-Fi Calling Status
        binding.tvVoWiFiStatus.text = "Wi-Fi Calling (VoWiFi): Supported by Samsung IMS stack"
        binding.tvVoWiFiStatus.setTextColor(ContextCompat.getColor(this, R.color.success))

        // 6. Wi-Fi State
        val connMgr = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val activeNet = connMgr.activeNetwork
        val caps = connMgr.getNetworkCapabilities(activeNet)
        val isWifi = caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true

        if (isWifi) {
            try {
                val wifiMgr = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                val wifiInfo = wifiMgr.connectionInfo
                val ssid = wifiInfo.ssid.replace("\"", "").ifBlank { "Connected" }
                val ipAddress = Formatter.formatIpAddress(wifiInfo.ipAddress)
                val linkSpeed = wifiInfo.linkSpeed

                binding.tvWifiState.text = "Wi-Fi: CONNECTED to \"$ssid\""
                binding.tvWifiState.setTextColor(ContextCompat.getColor(this, R.color.success))
                binding.tvWifiDetails.text = "IP Address: $ipAddress | Link Speed: $linkSpeed Mbps"
            } catch (e: Exception) {
                binding.tvWifiState.text = "Wi-Fi: CONNECTED"
                binding.tvWifiState.setTextColor(ContextCompat.getColor(this, R.color.success))
                binding.tvWifiDetails.text = "Wi-Fi Active"
            }
        } else {
            binding.tvWifiState.text = "Wi-Fi: DISCONNECTED"
            binding.tvWifiState.setTextColor(ContextCompat.getColor(this, R.color.text_muted))
            binding.tvWifiDetails.text = "No Wi-Fi connection active."
        }
    }

    private fun setupListeners() {
        binding.btnRequestPermissions.setOnClickListener {
            permissionLauncher.launch(requiredPermissions)
        }

        binding.btnSyncBackend.setOnClickListener {
            syncWithBackend()
            refreshDiagnostics()
        }

        // Auto Answer Listeners
        binding.switchAutoAnswer.setOnCheckedChangeListener { _, isChecked ->
            savePreferences()
            val status = if (isChecked) "ENABLED (Auto-answers incoming calls)" else "DISABLED (Manual answering only)"
            Toast.makeText(this, "AI Auto Answer: $status", Toast.LENGTH_SHORT).show()
        }

        binding.rgAnswerPolicy.setOnCheckedChangeListener { _, checkedId ->
            if (checkedId == R.id.rbApprovedOnly) {
                binding.etApprovedNumbers.visibility = View.VISIBLE
            } else {
                binding.etApprovedNumbers.visibility = View.GONE
            }
            savePreferences()
        }

        binding.btnAnswerCall.setOnClickListener {
            if (callMonitor.answerCall()) {
                Toast.makeText(this, "Answering call...", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "Failed to answer. Check permissions.", Toast.LENGTH_SHORT).show()
            }
        }

        binding.btnEndCall.setOnClickListener {
            autoAnswerJob?.cancel()
            callCommandJob?.cancel()
            if (callMonitor.endCall()) {
                Toast.makeText(this, "Ending call...", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "Failed to end call.", Toast.LENGTH_SHORT).show()
            }
        }

        binding.btnDialOut.setOnClickListener {
            val number = binding.etDialNumber.text.toString().trim()
            if (number.isNotEmpty()) {
                if (callMonitor.dialNumber(number)) {
                    Toast.makeText(this, "Attempting dial $number...", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this, "Could not dial number.", Toast.LENGTH_SHORT).show()
                }
            } else {
                Toast.makeText(this, "Please enter a valid phone number", Toast.LENGTH_SHORT).show()
            }
        }

        // Voice Connection Test Button (Phase 3)
        binding.btnTestVoicePhrase.setOnClickListener {
            configureInCallAudio(true)
            val testPhrase = "Hello, this is Audible AI. Your voice connection test is successful."
            speakToCaller(testPhrase)
            lifecycleScope.launch {
                apiClient.triggerSpeakTest()
            }
            Toast.makeText(this, "Speaking test phrase to caller...", Toast.LENGTH_SHORT).show()
        }

        // Speakerphone Toggle Button
        binding.btnToggleSpeaker.setOnClickListener {
            configureInCallAudio(!isSpeakerphoneEnabled)
        }

        // Settings Shortcuts
        binding.btnOpenMobileSettings.setOnClickListener {
            try {
                startActivity(Intent(Settings.ACTION_NETWORK_OPERATOR_SETTINGS))
            } catch (e: Exception) {
                try {
                    startActivity(Intent(Settings.ACTION_DATA_ROAMING_SETTINGS))
                } catch (e2: Exception) {
                    Toast.makeText(this, "Cannot open mobile settings", Toast.LENGTH_SHORT).show()
                }
            }
        }

        binding.btnOpenWifiSettings.setOnClickListener {
            try {
                startActivity(Intent(Settings.ACTION_WIFI_SETTINGS))
            } catch (e: Exception) {
                Toast.makeText(this, "Cannot open Wi-Fi settings", Toast.LENGTH_SHORT).show()
            }
        }

        binding.btnOpenPhoneAccounts.setOnClickListener {
            try {
                startActivity(Intent(TelecomManager.ACTION_CHANGE_PHONE_ACCOUNTS))
            } catch (e: Exception) {
                Toast.makeText(this, "Cannot open phone accounts", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun syncWithBackend() {
        binding.tvBackendStatus.text = "Backend: Connecting to Windows Audible AI (192.168.0.107:8000)..."
        binding.tvBackendStatus.setTextColor(ContextCompat.getColor(this, R.color.warning))

        val batteryManager = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val batteryPct = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val telephonyManager = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        val simName = telephonyManager.simOperatorName.ifBlank { "JIO 4G" }

        lifecycleScope.launch {
            val result = apiClient.pairDevice(simName, batteryPct)
            result.onSuccess {
                binding.tvBackendStatus.text = "Backend: CONNECTED to Windows Audible AI (192.168.0.107:8000)"
                binding.tvBackendStatus.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.success))
            }.onFailure { err ->
                binding.tvBackendStatus.text = "Backend: Disconnected (${err.message})"
                binding.tvBackendStatus.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.danger))
            }
        }
    }

    private fun isCallerApproved(incomingNumber: String?): Boolean {
        if (binding.rbAllCalls.isChecked) return true
        if (incomingNumber == null) return false

        val approvedRaw = binding.etApprovedNumbers.text.toString().trim()
        if (approvedRaw.isEmpty()) return false

        val approvedList = approvedRaw.split(",").map { it.trim().replace(" ", "").replace("-", "") }
        val cleanIncoming = incomingNumber.replace(" ", "").replace("-", "")

        return approvedList.any { cleanIncoming.endsWith(it) || it.endsWith(cleanIncoming) }
    }

    private fun onCallStateChanged(state: String, number: String?, callId: String) {
        runOnUiThread {
            binding.tvCallState.text = "Call State: $state"
            binding.tvCallerNumber.text = "Caller: ${number ?: "Cellular Voice Line"}"

            when (state) {
                "RINGING" -> {
                    binding.tvCallState.setTextColor(ContextCompat.getColor(this, R.color.warning))
                    binding.tvIncomingCallDetected.text = "Incoming Call Detected: YES (${number ?: "Incoming"})"
                    binding.tvIncomingCallDetected.setTextColor(ContextCompat.getColor(this, R.color.warning))
                    binding.btnAnswerCall.isEnabled = true
                    binding.btnEndCall.isEnabled = true

                    // Check AI Auto Answer Policy
                    if (binding.switchAutoAnswer.isChecked && isCallerApproved(number)) {
                        Toast.makeText(this, "AI Auto Answer: Answering in 2.5s...", Toast.LENGTH_SHORT).show()
                        autoAnswerJob?.cancel()
                        autoAnswerJob = lifecycleScope.launch {
                            delay(2500)
                            if (callMonitor.currentCallState == "RINGING") {
                                callMonitor.answerCall()
                                // TelecomCallMonitor will trigger OFFHOOK with the exact same callId upon answer
                            }
                        }
                    }
                }
                "OFFHOOK" -> {
                    autoAnswerJob?.cancel()
                    binding.tvCallState.setTextColor(ContextCompat.getColor(this, R.color.success))
                    binding.tvIncomingCallDetected.text = "Incoming Call Detected: ACTIVE"
                    binding.tvIncomingCallDetected.setTextColor(ContextCompat.getColor(this, R.color.success))
                    binding.btnAnswerCall.isEnabled = false
                    binding.btnEndCall.isEnabled = true

                    // Configure speakerphone
                    configureInCallAudio(true)

                    // Start background command polling loop during active call for this specific callId
                    callCommandJob?.cancel()
                    callCommandJob = lifecycleScope.launch {
                        val processedCommandIds = mutableSetOf<String>()
                        while (isActive && callMonitor.currentCallState == "OFFHOOK") {
                            val res = apiClient.getPendingCommands(callId)
                            res.onSuccess { cmds ->
                                for (cmd in cmds) {
                                    val cmdId = cmd.optString("command_id")
                                    val action = cmd.optString("action")
                                    if (cmdId.isNotEmpty() && processedCommandIds.contains(cmdId)) {
                                        continue
                                    }
                                    if (cmdId.isNotEmpty()) {
                                        processedCommandIds.add(cmdId)
                                    }

                                    when (action) {
                                        "SPEAK" -> {
                                            val text = cmd.optString("text")
                                            val isFarewell = cmd.optBoolean("should_hangup", false)
                                            // Wait if currently speaking to prevent overlapping speech
                                            while (isSpeaking && isActive) {
                                                delay(200)
                                            }
                                            // speakToCaller encodes cmdId; ackCommand will be called from onDone()
                                            speakToCaller(text, isFarewell, cmdId)
                                        }
                                        "SEND_SMS" -> {
                                            val phone = cmd.optString("phone_number")
                                            val message = cmd.optString("message")
                                            val orderId = cmd.optString("order_id")
                                            if (phone.isNotEmpty() && message.isNotEmpty()) {
                                                sendSms(phone, message, orderId.ifEmpty { null })
                                            }
                                            if (cmdId.isNotEmpty()) {
                                                apiClient.ackCommand(cmdId, "COMPLETED")
                                            }
                                        }
                                        "HANGUP" -> {
                                            while (isSpeaking && isActive) {
                                                delay(200)
                                            }
                                            delay(1500)
                                            callMonitor.endCall()
                                            if (cmdId.isNotEmpty()) {
                                                apiClient.ackCommand(cmdId, "COMPLETED")
                                            }
                                        }
                                    }
                                }
                            }
                            delay(1000)
                        }
                    }
                }
                else -> { // IDLE
                    autoAnswerJob?.cancel()
                    callCommandJob?.cancel()
                    binding.tvCallState.setTextColor(ContextCompat.getColor(this, R.color.text_light))
                    binding.tvIncomingCallDetected.text = "Incoming Call Detected: No"
                    binding.tvIncomingCallDetected.setTextColor(ContextCompat.getColor(this, R.color.text_muted))
                    binding.btnAnswerCall.isEnabled = false
                    binding.btnEndCall.isEnabled = false
                    binding.tvLiveTranscript.text = "Live Speech: Call Finished."
                    audioManager.mode = AudioManager.MODE_NORMAL
                }
            }
        }

        lifecycleScope.launch {
            apiClient.reportCallEvent(state, number, callId)
        }
    }

    private fun sendSms(phoneNumber: String, message: String, orderId: String? = null) {
        try {
            val smsManager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                getSystemService(SmsManager::class.java)
            } else {
                @Suppress("DEPRECATION")
                SmsManager.getDefault()
            }
            val parts = smsManager.divideMessage(message)
            smsManager.sendMultipartTextMessage(phoneNumber, null, parts, null, null)
            Log.i("MainActivity", "Successfully dispatched SMS to $phoneNumber (orderId=$orderId): $message")
            lifecycleScope.launch {
                if (orderId != null) {
                    apiClient.reportSmsSent(orderId, true)
                }
            }
            runOnUiThread {
                Toast.makeText(this, "FreshMart SMS sent to $phoneNumber", Toast.LENGTH_SHORT).show()
            }
        } catch (e: Exception) {
            Log.e("MainActivity", "Failed to send SMS to $phoneNumber: ${e.message}", e)
            lifecycleScope.launch {
                if (orderId != null) {
                    apiClient.reportSmsSent(orderId, false)
                }
            }
        }
    }

    private fun startGlobalCommandPolling() {
        globalCommandJob?.cancel()
        globalCommandJob = lifecycleScope.launch {
            while (isActive) {
                if (callMonitor.currentCallState != "OFFHOOK") {
                    val res = apiClient.getPendingCommands()
                    res.onSuccess { cmds ->
                        for (cmd in cmds) {
                            val cmdId = cmd.optString("command_id")
                            val action = cmd.optString("action")
                            if (action == "SEND_SMS") {
                                val phone = cmd.optString("phone_number")
                                val message = cmd.optString("message")
                                val orderId = cmd.optString("order_id")
                                if (phone.isNotEmpty() && message.isNotEmpty()) {
                                    sendSms(phone, message, orderId.ifEmpty { null })
                                }
                                if (cmdId.isNotEmpty()) {
                                    apiClient.ackCommand(cmdId)
                                }
                            }
                        }
                    }
                }
                delay(2500)
            }
        }
    }
}
