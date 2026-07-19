package com.ali.englishassistant

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * Minimal client for the Gemini generateContent REST endpoint.
 * No SDK dependency so the APK stays tiny and the build stays simple.
 * All methods are blocking — call them from a background thread.
 */
object GeminiClient {

    /** Thrown when the configured model has been retired/renamed by Google (HTTP 404). */
    private class ModelUnavailableException(msg: String) : IOException(msg)

    /** Thrown on HTTP 429 (per-minute quota). Carries the server's suggested wait. */
    private class RateLimitException(val retryAfterMs: Long) : IOException("rate limited")

    /** One suggested reply: the English text to send, plus its natural Urdu meaning. */
    data class Reply(val english: String, val urdu: String)
    data class Result(val urdu: String, val replies: List<Reply>)

    /**
     * ONE AI call that returns BOTH a natural, human Urdu explanation of the
     * customer's message AND two professional English replies (each with its
     * Urdu meaning). Combining them keeps quota use low while giving
     * ChatGPT-quality understanding.
     */
    fun analyzeMessage(ctx: Context, message: String): Result {
        val prompt = """
            You are a smart bilingual assistant helping a Pakistani exporter who does NOT understand English.
            A customer sent him this chat message:

            "$message"

            Reply ONLY as JSON in exactly this shape (no other text):
            {"urdu": "...", "replies": [{"english": "...", "urdu": "..."}, {"english": "...", "urdu": "..."}]}

            - "urdu": Explain in clear, natural, conversational Urdu (Urdu script) what the customer really
              means and wants — the way a smart friend would explain it, capturing intent and tone. NOT a
              stiff word-for-word translation. 1-3 sentences. Understand business/social media terms
              (reel, edit, raw footage, sample, order, shipping, invoice) correctly.
            - "replies": exactly 2 short, polite, professional English replies he could send back, clearly
              different from each other (e.g. one accepting, one asking a useful question). Each item has
              "english" (the reply to send) and "urdu" (a natural Urdu meaning of that reply). No emojis.
        """.trimIndent()

        val text = generate(ctx, prompt, jsonMode = true)
        val obj = JSONObject(extractJson(text))
        val arr = obj.optJSONArray("replies") ?: JSONArray()
        val replies = ArrayList<Reply>()
        for (i in 0 until arr.length()) {
            val item = arr.opt(i)
            if (item is JSONObject) {
                val en = item.optString("english").trim()
                val ur = item.optString("urdu").trim()
                if (en.isNotEmpty()) replies.add(Reply(en, ur))
            }
        }
        return Result(obj.optString("urdu").trim(), replies)
    }

    /**
     * AI turns uncle's spoken Urdu into a polished, professional English chat
     * reply — context-aware, and it corrects obvious speech-recognition slips
     * (e.g. "rail" that should be "reel").
     */
    fun urduToEnglish(ctx: Context, urdu: String): String {
        val prompt = """
            A Pakistani exporter is replying to a business customer. He SPOKE the following in Urdu, so it
            came from voice recognition and may contain small mis-hearings — especially English business
            words written phonetically (e.g. "ریل/rail" almost always means "reel", "ایڈٹ" means "edit",
            "ویڈیو" means "video"). First understand what he actually means, correcting such slips:

            "$urdu"

            Then write ONE short, polite, natural, professional English chat message that conveys his
            intended meaning, with correct grammar and tone.
            Reply with ONLY the English message text — no quotes, no explanation, nothing else.
        """.trimIndent()
        return generate(ctx, prompt, jsonMode = false).trim().trim('"')
    }

    /** Quick connectivity/key test. Throws on failure. */
    fun test(ctx: Context) {
        generate(ctx, "Reply with only the word: OK", jsonMode = false)
    }

    /**
     * Runs the request with the saved model. If Google has retired that model
     * (404), asks the API which models this key can use, saves the best flash
     * model, and retries — so the app self-heals when models are renamed.
     */
    private fun generate(ctx: Context, prompt: String, jsonMode: Boolean): String {
        val key = Prefs.apiKey(ctx)
        if (key.isBlank()) throw IOException("No API key set")
        return try {
            callRetrying(key, Prefs.model(ctx), prompt, jsonMode)
        } catch (e: ModelUnavailableException) {
            var lastError: Exception = e
            for (candidate in discoverModels(key)) {
                try {
                    val result = callRetrying(key, candidate, prompt, jsonMode)
                    Prefs.saveModel(ctx, candidate)
                    return result
                } catch (err: ModelUnavailableException) {
                    lastError = err
                }
            }
            throw lastError
        }
    }

    /** Retries once on a 429 rate limit after a short, capped wait. */
    private fun callRetrying(apiKey: String, model: String, prompt: String, jsonMode: Boolean): String {
        return try {
            call(apiKey, model, prompt, jsonMode)
        } catch (e: RateLimitException) {
            // Wait the server's suggested delay, capped so the user isn't stuck long.
            Thread.sleep(e.retryAfterMs.coerceIn(1000L, 6000L))
            call(apiKey, model, prompt, jsonMode)
        }
    }

    /** Asks the API for available models; best free "flash" candidates first. */
    private fun discoverModels(apiKey: String): List<String> {
        val url = URL("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200")
        val conn = url.openConnection() as HttpURLConnection
        val resp = try {
            conn.connectTimeout = 15000
            conn.readTimeout = 30000
            conn.setRequestProperty("x-goog-api-key", apiKey)
            if (conn.responseCode !in 200..299) {
                throw IOException("Could not list models (HTTP ${conn.responseCode})")
            }
            conn.inputStream.bufferedReader().readText()
        } finally {
            conn.disconnect()
        }

        val models = JSONObject(resp).optJSONArray("models") ?: JSONArray()
        data class Candidate(val name: String, val version: Double, val lite: Boolean, val latest: Boolean)
        val candidates = ArrayList<Candidate>()
        for (i in 0 until models.length()) {
            val m = models.getJSONObject(i)
            val name = m.optString("name").removePrefix("models/")
            val methods = m.optJSONArray("supportedGenerationMethods")?.toString() ?: ""
            if (!methods.contains("generateContent")) continue
            if (!name.contains("flash")) continue
            // Skip specialised variants that don't do plain text chat well.
            if (listOf("image", "tts", "audio", "live", "embedding", "exp", "preview", "thinking", "omni", "robotics")
                    .any { name.contains(it) }) continue
            val version = Regex("gemini-(\\d+(?:\\.\\d+)?)").find(name)
                ?.groupValues?.get(1)?.toDoubleOrNull() ?: 0.0
            candidates.add(Candidate(name, version, name.contains("lite"), name.endsWith("-latest")))
        }
        if (candidates.isEmpty()) throw IOException("No usable model found for this API key")
        // "-latest" aliases first (never retired), then newest version, non-lite before lite.
        return candidates
            .sortedWith(compareByDescending<Candidate> { it.latest }
                .thenByDescending { it.version }
                .thenBy { it.lite })
            .map { it.name }
            .take(4)
    }

    private fun call(apiKey: String, model: String, prompt: String, jsonMode: Boolean): String {
        val url = URL("https://generativelanguage.googleapis.com/v1beta/models/$model:generateContent")
        val conn = url.openConnection() as HttpURLConnection
        try {
            conn.requestMethod = "POST"
            conn.connectTimeout = 15000
            conn.readTimeout = 30000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("x-goog-api-key", apiKey)

            val generationConfig = JSONObject().put("temperature", 0.4)
            if (jsonMode) generationConfig.put("responseMimeType", "application/json")

            val body = JSONObject()
                .put("contents", JSONArray().put(
                    JSONObject().put("parts", JSONArray().put(
                        JSONObject().put("text", prompt)))))
                .put("generationConfig", generationConfig)

            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }

            val code = conn.responseCode
            if (code !in 200..299) {
                val err = conn.errorStream?.bufferedReader()?.readText() ?: ""
                val msg = try {
                    JSONObject(err).getJSONObject("error").optString("message")
                } catch (e: Exception) { err.take(200) }
                if (code == 404) throw ModelUnavailableException("Model $model unavailable: $msg")
                if (code == 429) throw RateLimitException(parseRetryMs(err))
                throw IOException("API error $code: $msg")
            }

            val resp = conn.inputStream.bufferedReader().readText()
            val candidates = JSONObject(resp).optJSONArray("candidates")
                ?: throw IOException("No response from model")
            if (candidates.length() == 0) throw IOException("Empty response from model")
            val parts = candidates.getJSONObject(0)
                .getJSONObject("content")
                .getJSONArray("parts")
            val sb = StringBuilder()
            for (i in 0 until parts.length()) sb.append(parts.getJSONObject(i).optString("text"))
            return sb.toString()
        } finally {
            conn.disconnect()
        }
    }

    /** Pulls the "retryDelay" (e.g. "35s") out of a 429 body; defaults to 3s. */
    private fun parseRetryMs(errorBody: String): Long {
        val m = Regex("\"retryDelay\"\\s*:\\s*\"(\\d+)s\"").find(errorBody)
        val secs = m?.groupValues?.get(1)?.toLongOrNull() ?: 3L
        return secs * 1000L
    }

    /** Models sometimes wrap JSON in markdown fences even in JSON mode — strip them. */
    private fun extractJson(text: String): String {
        val t = text.trim()
        val start = t.indexOf('{')
        val end = t.lastIndexOf('}')
        if (start >= 0 && end > start) return t.substring(start, end + 1)
        throw IOException("Model did not return JSON: ${t.take(120)}")
    }
}
