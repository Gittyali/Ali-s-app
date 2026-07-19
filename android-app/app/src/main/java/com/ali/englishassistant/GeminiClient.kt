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

    /**
     * The ONLY use of AI in the app: suggest 2 English replies to the customer's
     * message. Translation to Urdu is done on-device (offline), not here, so a
     * quota error here never breaks translation — it only pauses suggestions.
     * Returns the English reply strings.
     */
    fun suggestReplies(ctx: Context, message: String): List<String> {
        val prompt = """
            A Pakistani exporter received this chat message from a customer:

            "$message"

            Suggest exactly 2 short, polite, professional one-line English replies he could send back.
            Make them different from each other (e.g. one positive/accepting, one asking for a detail).
            Reply ONLY with a JSON array of 2 strings, no other text, like:
            ["reply one", "reply two"]
            No emojis, no extra keys.
        """.trimIndent()

        val text = generate(ctx, prompt, jsonMode = true)
        val arr = parseArray(text)
        val replies = ArrayList<String>()
        for (i in 0 until arr.length()) {
            val item = arr.opt(i)
            val en = if (item is JSONObject) item.optString("english").trim()
                     else arr.optString(i).trim()
            if (en.isNotEmpty()) replies.add(en)
        }
        return replies
    }

    private fun parseArray(text: String): JSONArray {
        val t = text.trim()
        val start = t.indexOf('[')
        val end = t.lastIndexOf(']')
        if (start >= 0 && end > start) return JSONArray(t.substring(start, end + 1))
        // Some models wrap the array in an object like {"replies": [...]}.
        val obj = JSONObject(extractJson(t))
        return obj.optJSONArray("replies") ?: JSONArray()
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
