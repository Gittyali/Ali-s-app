package com.ali.englishassistant

/**
 * Screens a message BEFORE it is sent to the AI API.
 * Anything that looks like card/financial data or an OTP/password is
 * BLOCKED — never sent anywhere. Other long numbers are redacted as a
 * fallback. Detection is deliberately safety-first (a few false positives
 * are acceptable; a leaked card number is not).
 */
object Redactor {

    enum class Reason { NONE, OTP, FINANCIAL }

    data class Result(
        val text: String,
        val redacted: Boolean,
        val blocked: Boolean,
        val reason: Reason
    )

    private val otpContext = Regex(
        "\\b(otp|one[- ]?time|verification code|security code|login code|passcode|pin code|password)\\b",
        RegexOption.IGNORE_CASE
    )
    private val shortCode = Regex("\\b\\d{4,8}\\b")

    // Card-number-shaped: 13-19 digits, optionally split by spaces or dashes.
    private val cardLike = Regex("\\b\\d(?:[ -]?\\d){12,18}\\b")
    // CVV / CVC context followed by 3-4 digits.
    private val cvv = Regex("\\b(cvv|cvc|cvv2|cid|security code)\\b\\D{0,12}\\d{3,4}", RegexOption.IGNORE_CASE)
    // Expiry dates like 09/27 or 09-2027, and "exp/expiry ..." context.
    private val expiry = Regex("\\b(0[1-9]|1[0-2])[/\\-.](\\d{2}|\\d{4})\\b")
    private val expiryWord = Regex("\\b(exp|expiry|expiration|valid thru|valid through)\\b", RegexOption.IGNORE_CASE)
    private val cardWord = Regex("\\b(card ?number|debit card|credit card|card no)\\b", RegexOption.IGNORE_CASE)
    private val iban = Regex("\\b[A-Z]{2}\\d{2}[A-Z0-9]{10,30}\\b")
    private val cnic = Regex("\\b\\d{5}-\\d{7}-\\d\\b")
    private val longDigits = Regex("\\b\\d{14,}\\b")

    fun clean(input: String): Result {
        // 1. OTP / password → never sent.
        if (otpContext.containsMatchIn(input) && shortCode.containsMatchIn(input)) {
            return Result(input, redacted = false, blocked = true, reason = Reason.OTP)
        }

        // 2. Card / financial data → never sent. Any card-shaped number counts,
        //    even without the Luhn checksum, plus CVV, expiry, IBAN, CNIC, and
        //    card keywords.
        val looksFinancial =
            cardLike.containsMatchIn(input) ||
            cvv.containsMatchIn(input) ||
            expiry.containsMatchIn(input) ||
            iban.containsMatchIn(input) ||
            cnic.containsMatchIn(input) ||
            (cardWord.containsMatchIn(input) && Regex("\\d{3,}").containsMatchIn(input)) ||
            (expiryWord.containsMatchIn(input) && Regex("\\d{2,}").containsMatchIn(input))
        if (looksFinancial) {
            return Result(input, redacted = false, blocked = true, reason = Reason.FINANCIAL)
        }

        // 3. Any other very long digit run → redact but still allow translation.
        var redacted = false
        val t = longDigits.replace(input) { redacted = true; "[نمبر]" }
        return Result(t, redacted, blocked = false, reason = Reason.NONE)
    }
}
