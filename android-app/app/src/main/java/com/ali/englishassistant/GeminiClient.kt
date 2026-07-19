package com.ali.englishassistant

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

    data class Analysis(val urdu: String, val replies: List<String>)

    fun analyzeMessage(apiKey: String, model: String, message: String): Analysis {
        val prompt = """
            You are helping a Pakistani exporter who does not understand English.
            A customer sent him this chat message:

            "$message"

            Reply ONLY with a JSON object, no other text, in this exact shape:
            {"urdu": "...", "replies": ["...", "..."]}

            Rules:
            - "urdu": explain in simple, natural Urdu (Urdu script) what the customer is saying or asking. Keep it short (1-2 sentences).
            - "replies": exactly 2 short, polite, professional one-line English replies he could send back. Make them different from each other (e.g. one positive/accepting, one asking for detail). No emojis.
        """.trimIndent()

        val text = call(apiKey, model, prompt, jsonMode = true)
        val obj = JSONObject(extractJson(text))
        val repliesArr = obj.optJSONArray("replies") ?: JSONArray()
        val replies = ArrayList<String>()
        for (i in 0 until repliesArr.length()) {
            val r = repliesArr.optString(i).trim()
            if (r.isNotEmpty()) replies.add(r)
        }
        return Analysis(obj.optString("urdu").trim(), replies)
    }

    fun urduToEnglish(apiKey: String, model: String, urdu: String): String {
        val prompt = """
            A Pakistani exporter wants to reply to a business customer. He said this in Urdu:

            "$urdu"

            Translate it into one short, polite, natural, professional English chat message.
            Reply with ONLY the English message text — no quotes, no explanation, nothing else.
        """.trimIndent()
        return call(apiKey, model, prompt, jsonMode = false).trim().trim('"')
    }

    /** Quick connectivity/key test. Throws on failure. */
    fun test(apiKey: String, model: String) {
        analyzeMessage(apiKey, model, "Hello, how are you?")
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
