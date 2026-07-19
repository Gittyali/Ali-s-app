package com.ali.englishassistant

import android.accessibilityservice.AccessibilityService
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.util.Locale
import kotlin.math.abs

class AssistantService : AccessibilityService(), TextToSpeech.OnInitListener {

    private lateinit var wm: WindowManager
    private var bubble: View? = null
    private var panel: View? = null
    private var panelContent: LinearLayout? = null
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var recognizer: SpeechRecognizer? = null
    private val main = Handler(Looper.getMainLooper())
    private val density: Float get() = resources.displayMetrics.density

    // React instantly when the app toggles the assistant on/off.
    private val prefsListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == Prefs.KEY_ENABLED) main.post { applyEnabledState() }
    }

    // When the screen turns off, hide the bubble (and stop reading). Bring it
    // back when the phone wakes — without changing the user's on/off choice.
    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                Intent.ACTION_SCREEN_OFF -> main.post { hideBubbleTransient() }
                Intent.ACTION_USER_PRESENT, Intent.ACTION_SCREEN_ON ->
                    main.post { applyEnabledState() }
            }
        }
    }

    override fun onServiceConnected() {
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
        tts = TextToSpeech(this, this)
        Prefs.prefs(this).registerOnSharedPreferenceChangeListener(prefsListener)
        registerReceiver(screenReceiver, IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_USER_PRESENT)
        })
        // Pre-download the offline translation models so the first use is fast.
        Thread { runCatching { Translator.warmUp() } }.start()
        applyEnabledState()
    }

    /** Remove the bubble and any panel without touching the user's on/off pref. */
    private fun hideBubbleTransient() {
        removePanel()
        bubble?.let { runCatching { wm.removeView(it) } }
        bubble = null
    }

    /** Show the bubble when enabled; hide it (and any open panel) when paused. */
    private fun applyEnabledState() {
        if (Prefs.enabled(this)) {
            showBubble()
        } else {
            removePanel()
            bubble?.let { runCatching { wm.removeView(it) } }
            bubble = null
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val r = tts?.setLanguage(Locale("ur", "PK")) ?: TextToSpeech.LANG_NOT_SUPPORTED
            ttsReady = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() {}

    override fun onDestroy() {
        runCatching { Prefs.prefs(this).unregisterOnSharedPreferenceChangeListener(prefsListener) }
        runCatching { unregisterReceiver(screenReceiver) }
        removePanel()
        bubble?.let { runCatching { wm.removeView(it) } }
        bubble = null
        tts?.shutdown()
        recognizer?.destroy()
        super.onDestroy()
    }

    // ---------------- Floating bubble ----------------

    private fun showBubble() {
        if (bubble != null) return
        val size = dp(56)
        val view = TextView(this).apply {
            text = "💬"
            textSize = 26f
            gravity = Gravity.CENTER
            setBackgroundResource(R.drawable.bubble_bg)
        }
        val lp = WindowManager.LayoutParams(
            size, size,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = resources.displayMetrics.widthPixels - size - dp(8)
            y = resources.displayMetrics.heightPixels / 3
        }

        var downX = 0f; var downY = 0f; var startX = 0; var startY = 0
        var moved = false; var longPressed = false
        val longPress = Runnable {
            if (!moved) { longPressed = true; pauseFromBubble() }
        }
        view.setOnTouchListener { v, e ->
            when (e.action) {
                MotionEvent.ACTION_DOWN -> {
                    downX = e.rawX; downY = e.rawY; startX = lp.x; startY = lp.y
                    moved = false; longPressed = false
                    main.postDelayed(longPress, 700)  // hold to pause
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = e.rawX - downX; val dy = e.rawY - downY
                    if (abs(dx) > dp(6) || abs(dy) > dp(6)) {
                        moved = true
                        main.removeCallbacks(longPress)
                    }
                    lp.x = startX + dx.toInt(); lp.y = startY + dy.toInt()
                    runCatching { wm.updateViewLayout(v, lp) }
                    true
                }
                MotionEvent.ACTION_UP -> {
                    main.removeCallbacks(longPress)
                    if (!moved && !longPressed) onBubbleTapped()
                    true
                }
                else -> false
            }
        }
        runCatching { wm.addView(view, lp) }
        bubble = view
    }

    /** Long-press on the bubble pauses the assistant (bubble disappears). */
    private fun pauseFromBubble() {
        Prefs.setEnabled(this, false)  // listener removes the bubble
        toast("⏸ بند کر دیا — دوبارہ چالو کرنے کے لیے English Assistant ایپ کھولیں\nPaused — open the English Assistant app to turn it back on")
    }

    private fun onBubbleTapped() {
        if (panel != null) { removePanel(); return }
        // Security: only ever read inside known chat apps. Banking apps,
        // documents, settings etc. are refused here AND blocked by the
        // packageNames filter in the accessibility config (OS-enforced).
        val activePackage = rootInActiveWindow?.packageName?.toString() ?: ""
        if (activePackage !in ALLOWED_APPS) {
            showPanel()
            setPanelTitle("🔒 حفاظت • Protected")
            addNote("یہ ایپ صرف چیٹ ایپس میں کام کرتی ہے (WhatsApp، TikTok، Instagram، Facebook)۔ باقی ایپس نہیں پڑھی جاتیں۔\n\nFor your safety this assistant only works inside chat apps. It cannot read banking apps, documents, or anything else.")
            return
        }
        // Read the chat screen NOW, while the chat app is still the active window.
        val messages = collectVisibleTexts()
        showPanel()
        if (messages.isEmpty()) {
            setPanelTitle("کوئی پیغام نہیں ملا • No messages found")
            addNote("چیٹ کھول کر دوبارہ کوشش کریں\nOpen a chat and try again")
        } else {
            showMessageList(messages)
        }
    }

    // ---------------- Screen reading ----------------

    private fun collectVisibleTexts(): List<String> {
        val root = rootInActiveWindow ?: return emptyList()
        val out = LinkedHashSet<String>()
        walk(root, out, 0)
        return out.filter { it.length in 2..500 }
            .filterNot { it.matches(Regex("^[\\d:. /,-]+$")) }  // timestamps etc.
            .takeLast(6)
            .reversed()  // newest (bottom of screen) first
    }

    private fun walk(node: AccessibilityNodeInfo?, out: MutableSet<String>, depth: Int) {
        if (node == null || depth > 40) return
        if (node.isVisibleToUser && !node.isEditable && !node.isPassword) {
            val t = node.text?.toString()?.trim()
            if (!t.isNullOrEmpty()) out.add(t)
        }
        for (i in 0 until node.childCount) walk(node.getChild(i), out, depth + 1)
    }

    private fun findChatInput(): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(root)
        var steps = 0
        while (queue.isNotEmpty() && steps < 500) {
            steps++
            val n = queue.removeFirst()
            if (n.isEditable && n.isVisibleToUser) return n
            for (i in 0 until n.childCount) n.getChild(i)?.let { queue.add(it) }
        }
        return null
    }

    // ---------------- Panel UI ----------------

    private var titleView: TextView? = null

    private fun showPanel() {
        if (panel != null) return
        val outer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundResource(R.drawable.panel_bg)
            setPadding(dp(16), dp(12), dp(16), dp(16))
        }

        val header = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        titleView = TextView(this).apply {
            textSize = 16f
            setTypeface(null, Typeface.BOLD)
            setTextColor(Color.parseColor("#1B7A43"))
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        val close = TextView(this).apply {
            text = "✕"
            textSize = 20f
            setTextColor(Color.DKGRAY)
            setPadding(dp(12), 0, dp(4), 0)
            setOnClickListener { removePanel() }
        }
        header.addView(titleView)
        header.addView(close)
        outer.addView(header)

        val scroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(400)
            )
        }
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        scroll.addView(content)
        outer.addView(scroll)
        panelContent = content

        val lp = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.BOTTOM }

        runCatching { wm.addView(outer, lp) }
        panel = outer
    }

    private fun removePanel() {
        recognizer?.destroy(); recognizer = null
        panel?.let { runCatching { wm.removeView(it) } }
        panel = null; panelContent = null; titleView = null
    }

    private fun setPanelTitle(t: String) { titleView?.text = t }

    private fun clearContent() { panelContent?.removeAllViews() }

    private fun addNote(text: String, color: Int = Color.DKGRAY, size: Float = 15f): TextView {
        val tv = TextView(this).apply {
            this.text = text
            textSize = size
            setTextColor(color)
            setPadding(dp(4), dp(8), dp(4), dp(8))
        }
        panelContent?.addView(tv)
        return tv
    }

    private fun addChip(text: String, grey: Boolean = false, onClick: () -> Unit): TextView {
        val tv = TextView(this).apply {
            this.text = text
            textSize = 16f
            setTextColor(Color.BLACK)
            setBackgroundResource(if (grey) R.drawable.chip_grey_bg else R.drawable.chip_bg)
            setPadding(dp(14), dp(12), dp(14), dp(12))
            val p = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
            )
            p.topMargin = dp(8)
            layoutParams = p
            setOnClickListener { onClick() }
        }
        panelContent?.addView(tv)
        return tv
    }

    /**
     * Renders one suggested reply inside a bordered box:
     *  - the English reply text (tap = type it into the chat)
     *  - its Urdu meaning as readable text (so uncle can read it)
     *  - a 🔊 button to hear the Urdu meaning (falls back to the text if voice fails)
     */
    private fun addReply(reply: ReplyItem) {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundResource(R.drawable.chip_bg)
            setPadding(dp(12), dp(10), dp(12), dp(10))
            val p = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
            )
            p.topMargin = dp(8)
            layoutParams = p
        }

        // English reply — tap to type into chat.
        box.addView(TextView(this).apply {
            text = reply.english
            textSize = 16f
            setTextColor(Color.BLACK)
            setOnClickListener { insertIntoChat(reply.english) }
        })

        if (reply.urdu.isNotBlank()) {
            // Urdu meaning — readable text.
            box.addView(TextView(this).apply {
                text = reply.urdu
                textSize = 15f
                setTextColor(Color.parseColor("#1B7A43"))
                textDirection = View.TEXT_DIRECTION_RTL
                setPadding(0, dp(4), 0, dp(4))
            })
        }

        // Action row: type it / listen.
        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
            )
        }
        actions.addView(TextView(this).apply {
            text = "✍️ چیٹ میں لکھیں • Type"
            textSize = 14f
            setTextColor(Color.parseColor("#1B7A43"))
            setTypeface(null, Typeface.BOLD)
            setPadding(0, dp(6), dp(16), dp(2))
            setOnClickListener { insertIntoChat(reply.english) }
        })
        if (reply.urdu.isNotBlank()) {
            actions.addView(TextView(this).apply {
                text = "🔊 سنیں • Listen"
                textSize = 14f
                setTextColor(Color.parseColor("#1B7A43"))
                setTypeface(null, Typeface.BOLD)
                setPadding(0, dp(6), 0, dp(2))
                setOnClickListener { speakUrdu(reply.urdu) }
            })
        }
        box.addView(actions)
        panelContent?.addView(box)
    }

    // ---------------- Flows ----------------

    private fun showMessageList(messages: List<String>) {
        setPanelTitle("پیغام منتخب کریں • Choose a message")
        clearContent()
        for (m in messages) {
            val label = if (m.length > 120) m.take(120) + "…" else m
            addChip(label, grey = true) { analyze(m) }
        }
    }

    private fun analyze(message: String) {
        // Security: scrub card/account/ID numbers before anything leaves the
        // phone, and refuse to send OTP/password messages at all.
        val safe = Redactor.clean(message)
        if (safe.blocked) {
            setPanelTitle("🔒 حفاظت • Protected")
            clearContent()
            val note = if (safe.reason == Redactor.Reason.FINANCIAL)
                "یہ پیغام کارڈ نمبر، CVV یا میعاد جیسی مالی معلومات لگتا ہے، اس لیے حفاظت کے لیے کہیں نہیں بھیجا گیا۔\n\nThis looks like card / financial information (card number, CVV, or expiry), so for your safety it was NOT sent anywhere."
            else
                "یہ پیغام OTP یا پاس ورڈ لگتا ہے، اس لیے حفاظت کے لیے کہیں نہیں بھیجا گیا۔\n\nThis looks like an OTP/password message, so for your safety it was NOT sent anywhere."
            addNote(note)
            return
        }
        currentSafeMessage = safe.text
        currentOriginalMessage = message
        // Show the instant offline translation as a quick preview, then upgrade
        // it in place to a natural AI explanation. ONE AI call returns both the
        // human-style Urdu explanation AND the 2 replies, keeping quota low.
        setPanelTitle("ترجمہ ہو رہا ہے… • Translating…")
        clearContent()
        addNote("⏳ …")
        Thread {
            val offline = runCatching { Translator.toUrdu(message) }.getOrNull()
            main.post { renderMeaning(message, offline, safe.redacted, isAi = false) }

            if (Prefs.apiKey(this).isBlank()) {
                main.post { showReplies(emptyList(), noKey = true) }
                return@Thread
            }
            val result = runCatching { GeminiClient.analyzeMessage(this, safe.text) }.getOrNull()
            main.post {
                if (result != null && result.urdu.isNotBlank()) {
                    // Upgrade the translation to the natural AI version, in place.
                    updateMeaningToAi(result.urdu)
                    showReplies(result.replies.map { ReplyItem(it.english, it.urdu) })
                } else {
                    // AI busy/limited — keep the offline preview, show retry for replies.
                    showReplies(emptyList())
                }
            }
        }.start()
    }

    private data class ReplyItem(val english: String, val urdu: String)

    private var repliesLoadingView: TextView? = null
    private var meaningUrduView: TextView? = null
    private var meaningTagView: TextView? = null
    private var currentMeaningUrdu: String = ""
    private var currentSafeMessage: String = ""
    private var currentOriginalMessage: String = ""

    private fun renderMeaning(original: String, urdu: String?, redacted: Boolean, isAi: Boolean) {
        if (panel == null) return
        setPanelTitle("ترجمہ • Translation")
        clearContent()
        if (redacted) {
            addNote("🔒 حساس نمبر چھپا کر بھیجے گئے • Sensitive numbers were hidden", Color.parseColor("#1B7A43"), 12f)
        }
        addNote("“${if (original.length > 90) original.take(90) + "…" else original}”", Color.GRAY, 13f)

        // A small tag showing whether this is the quick offline version or the
        // better AI one.
        meaningTagView = addNote(
            if (isAi) "🤖 AI" else "⏳ فوری ترجمہ — AI بہتر بنا رہا ہے… • quick translation — AI improving…",
            Color.GRAY, 11f
        )

        currentMeaningUrdu = urdu ?: ""
        if (urdu.isNullOrBlank()) {
            meaningUrduView = addNote("ایک بار انٹرنیٹ آن کریں، پھر دوبارہ ٹیپ کریں\nTurn on internet once, then tap again.", Color.RED, 15f)
        } else {
            meaningUrduView = addNote(urdu, Color.BLACK, 19f).also {
                it.textDirection = View.TEXT_DIRECTION_RTL
            }
            addChip("🔊 سنیں • Listen") { speakUrdu(currentMeaningUrdu) }
        }
        // Placeholder while the AI replies load in the background.
        repliesLoadingView = addNote("⏳ جواب تیار ہو رہے ہیں… • Preparing replies…", Color.GRAY, 14f)
    }

    /** Replace the offline preview text with the natural AI explanation, in place. */
    private fun updateMeaningToAi(aiUrdu: String) {
        if (panel == null) return
        currentMeaningUrdu = aiUrdu
        meaningTagView?.text = "🤖 AI"
        meaningUrduView?.apply {
            text = aiUrdu
            setTextColor(Color.BLACK)
            textDirection = View.TEXT_DIRECTION_RTL
        }
    }

    private fun showReplies(replies: List<ReplyItem>, noKey: Boolean = false) {
        if (panel == null) return
        repliesLoadingView?.let { panelContent?.removeView(it) }
        repliesLoadingView = null

        if (noKey) {
            addNote("تجویز کردہ جواب کے لیے ایپ میں API کلید لگائیں — یا اپنا جواب بولیں\nAdd an API key in the app for suggested replies — or speak your own", Color.GRAY, 14f)
        } else if (replies.isEmpty()) {
            addNote("تجویز کردہ جواب ابھی نہیں آئے (AI کی فی منٹ حد پوری) — ایک منٹ بعد دوبارہ کوشش کریں\nSuggested replies didn't load (AI per-minute limit reached) — wait a minute and try again", Color.GRAY, 14f)
            addChip("🔄 جواب دوبارہ لائیں • Try again for replies") { analyze(currentOriginalMessage) }
        } else {
            addNote("جواب منتخب کریں — خود چیٹ میں لکھا جائے گا\nPick a reply — it will be typed into the chat:", Color.parseColor("#1B7A43"), 14f)
            for (r in replies) addReply(r)
        }
        addChip("🎤 اپنا جواب اردو میں بولیں • Speak your own reply in Urdu", grey = true) {
            startListening()
        }
    }

    private fun speakUrdu(text: String) {
        // If Urdu voice isn't available, don't error — the text is already on
        // screen for the user to read.
        if (ttsReady) {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "urdu")
        } else {
            toast("اردو آواز دستیاب نہیں — تحریر پڑھ لیں\nUrdu voice not available — please read the text")
        }
    }

    // ---------------- Insert reply into the chat app ----------------

    private fun insertIntoChat(text: String) {
        val activePackage = rootInActiveWindow?.packageName?.toString() ?: ""
        if (activePackage !in ALLOWED_APPS) {
            copyToClipboard(text)
            removePanel()
            toast("کاپی ہو گیا — چیٹ باکس میں Paste کریں • Copied — paste it in the chat box")
            return
        }
        val input = findChatInput()
        if (input != null) {
            input.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
            val args = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
            }
            val ok = input.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
            if (ok) {
                removePanel()
                toast("✅ لکھ دیا — اب Send دبائیں • Typed! Now press Send")
                return
            }
            // Fallback: clipboard + paste
            copyToClipboard(text)
            val pasted = input.performAction(AccessibilityNodeInfo.ACTION_PASTE)
            removePanel()
            toast(if (pasted) "✅ لکھ دیا — اب Send دبائیں • Now press Send"
                  else "کاپی ہو گیا — چیٹ باکس میں دیر تک دبا کر Paste کریں\nCopied — long-press the chat box and Paste")
            return
        }
        copyToClipboard(text)
        removePanel()
        toast("کاپی ہو گیا — چیٹ باکس میں دیر تک دبا کر Paste کریں\nCopied — long-press the chat box and Paste")
    }

    private fun copyToClipboard(text: String) {
        val cm = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText("reply", text))
    }

    // ---------------- Urdu voice input ----------------

    private fun startListening() {
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) !=
            android.content.pm.PackageManager.PERMISSION_GRANTED) {
            toast("مائیک کی اجازت نہیں — ایپ کھول کر اجازت دیں\nMicrophone not allowed — open the app to allow it")
            return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            toast("Voice recognition not available on this phone")
            return
        }
        setPanelTitle("🎤 سن رہا ہوں… اردو میں بولیں • Listening… speak in Urdu")
        clearContent()
        addNote("بولیں، پھر ⏹ دبائیں — یا غلطی ہو تو 🔄 دبا کر دوبارہ شروع کریں\nSpeak, then tap ⏹ to finish — or tap 🔄 to start over if you made a mistake.")
        // Manual controls so uncle can stop when done, or restart if he errs.
        addChip("⏹ مکمل • Done / Stop") { recognizer?.stopListening() }
        addChip("🔄 دوبارہ شروع کریں • Restart", grey = true) { startListening() }

        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onResults(results: Bundle?) {
                    val heard = results
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.firstOrNull()
                    if (heard.isNullOrBlank()) {
                        onVoiceError()
                    } else {
                        translateSpokenUrdu(heard)
                    }
                }
                override fun onError(error: Int) { onVoiceError() }
                override fun onReadyForSpeech(params: Bundle?) {}
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() { setPanelTitle("⏳ ترجمہ ہو رہا ہے… • Translating…") }
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ur-PK")
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            }
            startListening(intent)
        }
    }

    private fun onVoiceError() {
        setPanelTitle("سنائی نہیں دیا • Didn't catch that")
        clearContent()
        addChip("🎤 دوبارہ بولیں • Speak again") { startListening() }
    }

    private fun translateSpokenUrdu(urdu: String) {
        setPanelTitle("⏳ ترجمہ ہو رہا ہے… • Translating…")
        clearContent()
        addNote("آپ نے کہا: $urdu", Color.GRAY, 14f)
        Thread {
            // AI turns it into a professional English reply (context-aware).
            // If the AI is momentarily rate-limited, fall back to offline
            // translation so uncle still gets something usable.
            var aiUsed = true
            val english = runCatching { GeminiClient.urduToEnglish(this, urdu) }.getOrNull()
                ?: run { aiUsed = false; runCatching { Translator.toEnglish(urdu) }.getOrNull() }
            main.post {
                if (panel == null) return@post
                if (english.isNullOrBlank()) {
                    setPanelTitle("مسئلہ ہو گیا • Error")
                    clearContent()
                    addNote("ایک بار انٹرنیٹ آن کریں اور دوبارہ کوشش کریں\nTurn on internet once and try again.", Color.RED)
                    addChip("🎤 دوبارہ کوشش کریں • Try again") { startListening() }
                    return@post
                }
                setPanelTitle("انگریزی جواب • English reply")
                clearContent()
                addNote("آپ نے کہا: $urdu", Color.GRAY, 14f)
                if (!aiUsed) {
                    addNote("(AI مصروف تھا — سادہ ترجمہ استعمال ہوا)\n(AI busy — used simple translation)", Color.GRAY, 12f)
                }
                addNote(english, Color.BLACK, 17f)
                addChip("✍️ چیٹ میں لکھیں • Type into chat") { insertIntoChat(english) }
                if (!aiUsed) {
                    addChip("🤖 AI سے بہتر بنائیں • Improve with AI", grey = true) { translateSpokenUrdu(urdu) }
                }
                addChip("🎤 دوبارہ بولیں • Speak again", grey = true) { startListening() }
            }
        }.start()
    }

    // ---------------- Helpers ----------------

    private fun dp(v: Int): Int = (v * density).toInt()

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_LONG).show()

    companion object {
        /** The only apps this assistant is allowed to read from or type into. */
        val ALLOWED_APPS = setOf(
            "com.whatsapp",                 // WhatsApp
            "com.whatsapp.w4b",             // WhatsApp Business
            "com.zhiliaoapp.musically",     // TikTok
            "com.ss.android.ugc.trill",     // TikTok (Asia build)
            "com.instagram.android",        // Instagram
            "com.facebook.orca",            // Messenger
            "com.facebook.mlite",           // Messenger Lite
            "com.facebook.katana",          // Facebook
            "com.facebook.lite",            // Facebook Lite
            "org.telegram.messenger",       // Telegram
            "com.imo.android.imoim"         // imo
        )
    }
}
