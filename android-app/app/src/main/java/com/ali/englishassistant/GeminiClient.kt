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

    /** One suggested reply: the English text to send, plus its Urdu meaning. */
    data class Reply(val english: String, val urdu: String)
    data class Analysis(val urdu: String, val replies: List<Reply>)

    /** Thrown when the configured model has been retired/renamed by Google (HTTP 404). */
    private class ModelUnavailableException(msg: String) : IOException(msg)

    fun analyzeMessage(ctx: Context, message: String): Analysis {
        val prompt = """
            You are helping a Pakistani exporter who does not understand English.
            A customer sent him this chat message:

            "$message"

            Reply ONLY with a JSON object, no other text, in this exact shape:
            {"urdu": "...", "replies": [{"english": "...", "urdu": "..."}, {"english": "...", "urdu": "..."}]}

            Rules:
            - Top-level "urdu": explain in simple, natural Urdu (Urdu script) what the customer is saying or asking. Keep it short (1-2 sentences).
            - "replies": exactly 2 options. Each has "english" (a short, polite, professional one-line English reply he could send) and "urdu" (a short Urdu-script meaning of that same reply, so he understands what it says). Make the two replies different from each other (e.g. one positive/accepting, one asking for detail). No emojis.
        """.trimIndent()

        val text = generate(ctx, prompt, jsonMode = true)
        val obj = JSONObject(extractJson(text))
        val repliesArr = obj.optJSONArray("replies") ?: JSONArray()
        val replies = ArrayList<Reply>()
        for (i in 0 until repliesArr.length()) {
            // Accept both the new object form and, defensively, a plain string.
            val item = repliesArr.opt(i)
            if (item is JSONObject) {
                val en = item.optString("english").trim()
                val ur = item.optString("urdu").trim()
                if (en.isNotEmpty()) replies.add(Reply(en, ur))
            } else {
                val en = repliesArr.optString(i).trim()
                if (en.isNotEmpty()) replies.add(Reply(en, ""))
            }
        }
        return Analysis(obj.optString("urdu").trim(), replies)
    }

    fun urduToEnglish(ctx: Context, urdu: String): String {
        val prompt = """
            A Pakistani exporter wants to reply to a business customer. He said this in Urdu:

            "$urdu"

            Translate it into one short, polite, natural, professional English chat message.
            Reply with ONLY the English message text — no quotes, no explanation, nothing else.
        """.trimIndent()
        return generate(ctx, prompt, jsonMode = false).trim().trim('"')
    }

    /** Quick connectivity/key test. Throws on failure. */
    fun test(ctx: Context) {
        analyzeMessage(ctx, "Hello, how are you?")
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
            call(key, Prefs.model(ctx), prompt, jsonMode)
        } catch (e: ModelUnavailableException) {
            var lastError: Exception = e
            for (candidate in discoverModels(key)) {
                try {
                    val result = call(key, candidate, prompt, jsonMode)
                    Prefs.saveModel(ctx, candidate)
                    return result
                } catch (err: ModelUnavailableException) {
                    lastError = err
                }
            }
            throw lastError
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

    /** Models sometimes wrap JSON in markdown fences even in JSON mode — strip them. */
    private fun extractJson(text: String): String {
        val t = text.trim()
        val start = t.indexOf('{')
        val end = t.lastIndexOf('}')
        if (start >= 0 && end > start) return t.substring(start, end + 1)
        throw IOException("Model did not return JSON: ${t.take(120)}")
    }
}
