package ai.audible.companion

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class SmsReceiver : BroadcastReceiver() {

    private val apiClient = CompanionApiClient()
    private val scope = CoroutineScope(Dispatchers.IO)

    override fun onReceive(context: Context?, intent: Intent?) {
        if (intent?.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent)
        if (messages.isNullOrEmpty()) return

        val fullMessage = StringBuilder()
        var senderNumber = ""

        for (sms in messages) {
            if (senderNumber.isEmpty()) {
                senderNumber = sms.displayOriginatingAddress ?: sms.originatingAddress ?: ""
            }
            fullMessage.append(sms.displayMessageBody ?: sms.messageBody ?: "")
        }

        val text = fullMessage.toString().trim()
        Log.i("SmsReceiver", "Inbound SMS received from $senderNumber: $text")

        // Forward to Audible AI Windows Backend
        scope.launch {
            try {
                val res = apiClient.reportInboundSms(senderNumber, text)
                res.onSuccess { json ->
                    Log.i("SmsReceiver", "Backend processed inbound SMS: ${json.optString("action")} -> ${json.optString("reply_sms")}")
                }.onFailure { e ->
                    Log.e("SmsReceiver", "Failed to forward SMS to backend: ${e.message}")
                }
            } catch (t: Throwable) {
                Log.e("SmsReceiver", "Exception reporting SMS", t)
            }
        }
    }
}
