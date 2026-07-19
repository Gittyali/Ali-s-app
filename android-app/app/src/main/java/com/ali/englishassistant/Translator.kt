package com.ali.englishassistant

import com.google.android.gms.tasks.Tasks
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.translate.TranslateLanguage
import com.google.mlkit.nl.translate.Translation

/**
 * On-device English <-> Urdu translation via Google ML Kit.
 * Fully offline once the language models are downloaded (a one-time ~30MB
 * fetch on first use). No API key, no quota, no network per translation.
 *
 * All methods BLOCK on the calling thread — call them from a background thread.
 */
object Translator {

    private val en2ur = Translation.getClient(
        com.google.mlkit.nl.translate.TranslatorOptions.Builder()
            .setSourceLanguage(TranslateLanguage.ENGLISH)
            .setTargetLanguage(TranslateLanguage.URDU)
            .build()
    )
    private val ur2en = Translation.getClient(
        com.google.mlkit.nl.translate.TranslatorOptions.Builder()
            .setSourceLanguage(TranslateLanguage.URDU)
            .setTargetLanguage(TranslateLanguage.ENGLISH)
            .build()
    )
    // No special requirements — allow download over Wi-Fi or mobile data.
    private val conditions = DownloadConditions.Builder().build()

    /** Pre-download both models in the background so the first real use is fast. */
    fun warmUp() {
        runCatching { Tasks.await(en2ur.downloadModelIfNeeded(conditions)) }
        runCatching { Tasks.await(ur2en.downloadModelIfNeeded(conditions)) }
    }

    fun toUrdu(text: String): String {
        Tasks.await(en2ur.downloadModelIfNeeded(conditions))
        return Tasks.await(en2ur.translate(text))
    }

    fun toEnglish(text: String): String {
        Tasks.await(ur2en.downloadModelIfNeeded(conditions))
        return Tasks.await(ur2en.translate(text))
    }
}
