# Security Rules

**Phase 0 deliverable (baseline).** The security rules every later phase must
follow. Audits and verification happen in Phase 6; these rules bind from Phase 1.

---

## 1. Secrets

- The AI provider key lives **only** on the backend's server-side secret store.
- **Never** in the APK, `BuildConfig`, resources, source control, logs, or client
  `.env`. `.env.example` files contain placeholders only.
- Any on-device secret (install identity, app-lock) uses **Android Keystore**.

## 2. Network

- **HTTPS/TLS only.** Cleartext traffic disabled (`usesCleartextTraffic=false`).
- Define an Android **Network Security Configuration**; optional cert pinning to
  our backend domain.
- Strict timeouts and bounded retries; no user-controlled request URLs (no SSRF).

## 3. Input validation (client AND server)

- Trim, normalise Unicode (NFC), reject null bytes and invalid control characters.
- Enforce character limits (message and reply) and request-body size limits.
- Strict JSON schemas; restrict accepted languages and enum values; reject
  unexpected fields where practical.
- Escape text for display; never build SQL/shell/HTML/prompts by unsafe
  concatenation. The client message is **data**, never instructions.

## 4. AI response handling

- Validate the structured JSON on the **server** and again on the **client**.
- Enforce max lengths; drop unknown fields; never render unvalidated AI output.
- On malformed/timed-out responses → sealed error state + friendly Urdu message.

## 5. Sensitive-data filter (local, pre-network)

Conservative best-effort block/warn for likely passwords, PINs, OTP/verification
codes, card numbers (Luhn), CVV, bank/IBAN, crypto seed phrases/private keys,
national ID, passport numbers, auth tokens, recovery codes, and highly sensitive
medical info. Uses accessibility password metadata + regex/checksums + EN/UR
keyword context. **Not claimed perfect.** When blocked: do not send; show Urdu
warning.

## 6. Logging (allowlist only)

**Never log:** chat content, translations, suggested replies, speech transcripts,
accessibility node text, API keys, tokens, or device identifiers.
**May log:** random request id, feature name, success/categorised failure,
redacted exception class, timing metrics without content.

## 7. Android component security

- Components **non-exported** unless they must be exported; exported ones validate
  intents strictly.
- Immutable `PendingIntent` flags.
- No unsafe `WebView`, no JS bridges; sanitise deep links; no world-readable files;
  no exposed internal `ContentProvider`.
- Backup rules exclude any sensitive data; consider disabling screenshots on
  screens showing private chat text (balanced against usability).

## 8. Backend security

- App integrity: **Firebase App Check + Play Integrity**; per-install anonymous id.
- Rate limiting per install + IP; request-size limits; abuse detection.
- Secure headers (Helmet or equivalent); **CORS disabled/tightly restricted**
  (mobile API).
- Strict request + response schema validation; timeouts and bounded retries.
- Dependency lockfiles; automated dependency + secret scanning.
- Generic external error messages; detailed **redacted** internal diagnostics.
- **No request/response body logging.**

## 9. Data retention

Message text in memory only for the active task; clear ViewModel state on dismiss;
no chat persistence by default; backend stores no bodies; a **Clear Temporary
Data** button is provided. Optional context window (FR-16) is tiny, encrypted,
temporary, and off by default.

## 10. Authentication interpretation

No user accounts/logins (owner's explicit choice). The unlocked device + explicit
user interaction is the local access boundary. Optional device-biometric app-lock
in Settings, **off by default**. The app authenticates its *installation* to the
backend via integrity protections + anonymous credentials, not a user account.
