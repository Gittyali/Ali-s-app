package com.ali.englishassistant

import android.content.Context

object Prefs {
    private const val FILE = "assistant_prefs"
    private const val KEY_API = "api_key"
    private const val KEY_MODEL = "model"
    const val KEY_ENABLED = "enabled"
    // Rolling alias maintained by Google — always points to the newest flash model.
    const val DEFAULT_MODEL = "gemini-flash-latest"

    fun prefs(ctx: Context) = ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    /** Whether the on-screen bubble is active. Defaults to on. */
    fun enabled(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_ENABLED, true)

    fun setEnabled(ctx: Context, on: Boolean) {
        prefs(ctx).edit().putBoolean(KEY_ENABLED, on).apply()
    }

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
