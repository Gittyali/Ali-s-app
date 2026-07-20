package com.ali.englishassistant

/**
 * Scrubs sensitive data from a message BEFORE it is sent to the AI API.
 * Card numbers, bank accounts, and ID numbers never leave the phone;
 * OTP/password messages are blocked from being sent entirely.
 */
object Redactor {

    data class Result(
        val text: String,
        val redacted: Boolean,
        val blocked: Boolean
    )

    private val otpContext = Regex(
        "\\b(otp|one[- ]?time|verification code|security code|login code|password|passcode|pin code)\\b",
        RegexOption.IGNORE_CASE
    )
    private val shortCode = Regex("\\b\\d{4,8}\\b")
    private val cardLike = Regex("\\b(?:\\d[ -]?){13,19}\\b")
    private val iban = Regex("\\b[A-Z]{2}\\d{2}[A-Z0-9]{10,30}\\b")
    private val cnic = Regex("\\b\\d{5}-\\d{7}-\\d\\b")
    private val longDigits = Regex("\\b\\d{14,}\\b")

    fun clean(input: String): Result {
        // OTP / password messages are never sent to the API at all.
        if (otpContext.containsMatchIn(input) && shortCode.containsMatchIn(input)) {
            return Result(input, redacted = false, blocked = true)
        }

        var redacted = false
        var t = cardLike.replace(input) { m ->
            if (luhnValid(m.value)) { redacted = true; "[کارڈ نمبر]" } else m.value
        }
        t = iban.replace(t) { redacted = true; "[اکاؤنٹ نمبر]" }
        t = cnic.replace(t) { redacted = true; "[شناختی نمبر]" }
        t = longDigits.replace(t) { redacted = true; "[نمبر]" }
        return Result(t, redacted, blocked = false)
    }

    /** Luhn checksum — true only for real payment-card numbers. */
    private fun luhnValid(raw: String): Boolean {
        val digits = raw.filter { it.isDigit() }
        if (digits.length !in 13..19) return false
        var sum = 0
        var alternate = false
        for (i in digits.length - 1 downTo 0) {
            var d = digits[i] - '0'
            if (alternate) {
                d *= 2
                if (d > 9) d -= 9
            }
            sum += d
            alternate = !alternate
        }
        return sum % 10 == 0
    }
}
