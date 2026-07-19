package com.ali.englishassistant

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import android.os.Handler
import android.os.Looper

class MainActivity : Activity() {

    private lateinit var apiKeyInput: EditText
    private lateinit var modelInput: EditText
    private lateinit var statusText: TextView
    private val main = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        apiKeyInput = findViewById(R.id.apiKeyInput)
        modelInput = findViewById(R.id.modelInput)
        statusText = findViewById(R.id.statusText)

        apiKeyInput.setText(Prefs.apiKey(this))
        modelInput.setText(Prefs.model(this))

        findViewById<Button>(R.id.saveBtn).setOnClickListener {
            Prefs.save(this, apiKeyInput.text.toString(), modelInput.text.toString())
            toast("Saved • محفوظ ہو گیا")
            refreshStatus()
        }

        findViewById<Button>(R.id.testBtn).setOnClickListener {
            Prefs.save(this, apiKeyInput.text.toString(), modelInput.text.toString())
            val key = Prefs.apiKey(this)
            if (key.isBlank()) { toast("Enter API key first • پہلے API کلید لگائیں"); return@setOnClickListener }
            toast("Testing… • ٹیسٹ ہو رہا ہے…")
            Thread {
                try {
                    GeminiClient.test(key, Prefs.model(this))
                    main.post { toast("✅ Key works! • کلید درست ہے") }
                } catch (e: Exception) {
                    main.post { toast("❌ ${e.message}") }
                }
            }.start()
        }

        findViewById<Button>(R.id.micBtn).setOnClickListener {
            if (hasMic()) toast("Microphone already allowed • اجازت پہلے سے ہے")
            else requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1)
        }

        findViewById<Button>(R.id.accessBtn).setOnClickListener {
            toast("Find \"English Assistant\" and turn it ON • فہرست میں English Assistant تلاش کر کے آن کریں")
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        refreshStatus()
    }

    private fun hasMic() =
        checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun refreshStatus() {
        val keyOk = Prefs.apiKey(this).isNotBlank()
        val micOk = hasMic()
        val accOk = isServiceEnabled(this)
        statusText.text = buildString {
            append(if (keyOk) "✅ API key saved\n" else "❌ API key missing • کلید نہیں ہے\n")
            append(if (micOk) "✅ Microphone allowed\n" else "❌ Microphone not allowed • مائیک کی اجازت نہیں\n")
            append(if (accOk) "✅ Assistant is ON — bubble is on screen\n" else "❌ Assistant is OFF • سروس بند ہے\n")
            if (keyOk && micOk && accOk) append("\n🎉 Ready! Open any chat and tap the 💬 bubble.\nتیار ہے! کوئی چیٹ کھول کر 💬 بٹن دبائیں۔")
        }
    }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_LONG).show()

    companion object {
        fun isServiceEnabled(ctx: Context): Boolean {
            val expected = "${ctx.packageName}/${AssistantService::class.java.name}"
            val enabled = Settings.Secure.getString(
                ctx.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ) ?: return false
            val splitter = TextUtils.SimpleStringSplitter(':')
            splitter.setString(enabled)
            for (s in splitter) if (s.equals(expected, ignoreCase = true)) return true
            return false
        }
    }
}
