package ai.audible.companion

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.telecom.TelecomManager
import android.telephony.PhoneStateListener
import android.telephony.TelephonyCallback
import android.telephony.TelephonyManager
import androidx.core.content.ContextCompat

class TelecomCallMonitor(
    private val context: Context,
    private val onStateChanged: (state: String, number: String?, callId: String) -> Unit
) {

    private val telephonyManager = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
    private val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as TelecomManager

    private var telephonyCallback: Any? = null
    private var phoneStateListener: PhoneStateListener? = null

    var currentCallState: String = "IDLE"
        private set

    var currentCallerNumber: String? = null
        private set

    fun startListening() {
        val hasPhonePermission = ContextCompat.checkSelfPermission(
            context,
            android.Manifest.permission.READ_PHONE_STATE
        ) == PackageManager.PERMISSION_GRANTED

        if (!hasPhonePermission) return

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val callback = object : TelephonyCallback(), TelephonyCallback.CallStateListener {
                override fun onCallStateChanged(state: Int) {
                    handleState(state, null)
                }
            }
            telephonyCallback = callback
            telephonyManager.registerTelephonyCallback(context.mainExecutor, callback)
        } else {
            @Suppress("DEPRECATION")
            val listener = object : PhoneStateListener() {
                @Deprecated("Deprecated in Java")
                override fun onCallStateChanged(state: Int, phoneNumber: String?) {
                    handleState(state, phoneNumber)
                }
            }
            phoneStateListener = listener
            @Suppress("DEPRECATION")
            telephonyManager.listen(listener, PhoneStateListener.LISTEN_CALL_STATE)
        }
    }

    fun stopListening() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            telephonyCallback?.let {
                telephonyManager.unregisterTelephonyCallback(it as TelephonyCallback)
            }
            telephonyCallback = null
        } else {
            phoneStateListener?.let {
                @Suppress("DEPRECATION")
                telephonyManager.listen(it, PhoneStateListener.LISTEN_NONE)
            }
            phoneStateListener = null
        }
    }

    private var lastStateStr: String = "IDLE"
    var currentCallSessionId: String = ""
        private set

    private fun handleState(state: Int, number: String?) {
        val stateStr = when (state) {
            TelephonyManager.CALL_STATE_RINGING -> "RINGING"
            TelephonyManager.CALL_STATE_OFFHOOK -> "OFFHOOK"
            TelephonyManager.CALL_STATE_IDLE -> "IDLE"
            else -> "UNKNOWN"
        }

        // Deduplicate duplicate callbacks from Android telephony framework
        if (stateStr == lastStateStr) {
            return
        }
        val prevState = lastStateStr
        lastStateStr = stateStr

        if ((stateStr == "RINGING" || stateStr == "OFFHOOK") && currentCallSessionId.isEmpty()) {
            currentCallSessionId = "call_" + System.currentTimeMillis()
        }

        val activeCallId = currentCallSessionId

        if (stateStr == "IDLE") {
            currentCallSessionId = ""
        }

        currentCallState = stateStr
        currentCallerNumber = number

        onStateChanged(stateStr, number, activeCallId)
    }

    @SuppressLint("MissingPermission")
    fun answerCall(): Boolean {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val hasPerm = ContextCompat.checkSelfPermission(
                    context,
                    android.Manifest.permission.ANSWER_PHONE_CALLS
                ) == PackageManager.PERMISSION_GRANTED
                if (hasPerm) {
                    telecomManager.acceptRingingCall()
                    true
                } else {
                    false
                }
            } else {
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    @SuppressLint("MissingPermission")
    fun endCall(): Boolean {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val hasPerm = ContextCompat.checkSelfPermission(
                    context,
                    android.Manifest.permission.ANSWER_PHONE_CALLS
                ) == PackageManager.PERMISSION_GRANTED
                if (hasPerm) {
                    telecomManager.endCall()
                } else {
                    false
                }
            } else {
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    @SuppressLint("MissingPermission")
    fun dialNumber(number: String): Boolean {
        return try {
            val hasPerm = ContextCompat.checkSelfPermission(
                context,
                android.Manifest.permission.CALL_PHONE
            ) == PackageManager.PERMISSION_GRANTED

            val uri = Uri.parse("tel:${Uri.encode(number)}")
            val intent = if (hasPerm) {
                Intent(Intent.ACTION_CALL, uri)
            } else {
                Intent(Intent.ACTION_DIAL, uri)
            }
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }
}
