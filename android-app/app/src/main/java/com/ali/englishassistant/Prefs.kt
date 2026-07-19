package com.ali.englishassistant

import android.content.Context

object Prefs {
    private const val FILE = "assistant_prefs"
    private const val KEY_API = "api_key"
    private const val KEY_MODEL = "model"
    const val DEFAULT_MODEL = "gemini-3-flash"

    fun apiKey(ctx: Context): String =
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY_API, "") ?: ""

    fun model(ctx: Context): String {
        val m = ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY_MODEL, "") ?: ""
        return if (m.isBlank()) DEFAULT_MODEL else m
    }

    fun saveModel(ctx: Context, model: String) {
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit()
            .putString(KEY_MODEL, model.trim())
            .apply()
    }

    fun save(ctx: Context, apiKey: String, model: String) {
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit()
            .putString(KEY_API, apiKey.trim())
            .putString(KEY_MODEL, model.trim())
            .apply()
    }
}
