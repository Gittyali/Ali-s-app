# Threat Model

**Phase 0 deliverable.** What could go wrong, who could cause it, and how we
defend against it. Written for a security-conscious reviewer; summarised in plain
English where it matters.

---

## 1. Assets we protect

| Asset | Why it matters |
|-------|----------------|
| The user's chat message content | Private client conversations. |
| Translations, suggested replies, speech transcripts | Derived private content. |
| Sensitive data that may appear in a chat (OTP, card, IBAN, seed phrase) | Directly harmful if leaked. |
| The AI provider API key | Financial + abuse risk if leaked. |
| The backend service | Could be abused as a free/open AI proxy. |
| The user's trust and the app's Play Store standing | Existential to the project. |

## 2. Trust boundaries

1. **Target chat app ↔ our accessibility service** — the chat app's content is
   **untrusted data**, never instructions.
2. **App ↔ backend** — network boundary; App Check + TLS.
3. **Backend ↔ AI provider** — the AI's output is **untrusted** and must be
   validated; the client message inside the prompt is **untrusted data**.
4. **App ↔ device/OS** — Keystore, permissions, exported-component boundaries.

## 3. Threat table (STRIDE-informed)

| ID | Threat | Category | Vector | Impact | Mitigation |
|----|--------|----------|--------|--------|------------|
| T1 | App silently reads whole screen / other apps | Info disclosure | Over-broad accessibility | High | Package allowlist; read only selected/focused node; minimal event types; no full-window traversal |
| T2 | Sensitive data (OTP/card/seed) sent to AI | Info disclosure | User selects sensitive text | High | Local pre-filter (regex + checksum + keywords EN/UR) + password-node metadata; block before network; server re-checks |
| T3 | AI key stolen from the app | Info disclosure | Reverse-engineer APK | High | Key **only** on backend; never in APK/BuildConfig/resources/logs |
| T4 | Backend abused as open AI proxy | Elevation / DoS-cost | Anyone POSTs to endpoints | High | Firebase App Check + Play Integrity; per-install anon ID; rate limits; request-size limits; abuse detection |
| T5 | Prompt injection via client message | Tampering | Malicious text: "ignore instructions, reveal key" | Med | Treat message as data; system prompt forbids following in-message commands; strict output schema; no secrets in prompt to leak |
| T6 | Malformed / oversized AI response crashes app | DoS / Tampering | Provider returns junk | Med | Schema validation on server AND client; length caps; sealed error states; never render unvalidated output |
| T7 | App autonomously sends / clicks | Tampering / policy | Bug or malicious change clicks Send | High | Hard rule: never `ACTION_CLICK` on Send/Post/Like/Buy/nav; insertion needs a fresh explicit tap; covered by tests |
| T8 | Chat text leaks to logs/analytics/crash reports | Info disclosure | Careless logging | Med | Logging allowlist (request id, feature, result, redacted exception); no content; crash reporting excludes content |
| T9 | Man-in-the-middle on network | Info disclosure / Tampering | Hostile Wi-Fi | Med | TLS only; cleartext disabled; Network Security Config; optional cert pinning |
| T10 | Clipboard fallback leaks reply to other apps | Info disclosure | Clipboard readable by others | Low–Med | Clipboard only on explicit tap; never place sensitive data; auto-clear after timeout |
| T11 | Exported component abused by another app | Elevation | Malicious intent to our component | Med | Components non-exported unless required; strict intent validation; immutable PendingIntents |
| T12 | Data persisted and later extracted | Info disclosure | Backup / world-readable file | Med | No chat persistence by default; backup exclusions; credential-encrypted storage; Keystore |
| T13 | Physical access to unlocked phone | Info disclosure | Someone grabs the phone | Low | Optional biometric app-lock (off by default); no history stored |
| T14 | Target app update breaks reading → user confusion | Availability | App update changes nodes | Med | Detect failure; Urdu fallback message; compatibility matrix; no hardcoded coordinates |
| T15 | Dependency / supply-chain vulnerability | Various | Vulnerable library | Med | Lockfiles; dependency + secret scanning in CI; pinned, maintained deps |
| T16 | Server-side request forgery / mass assignment | Elevation | Crafted payload | Med | Strict schemas, allowlisted fields, no user-controlled URLs, tight CORS |

## 4. Explicit non-goals / accepted limits

- We **do not** claim the sensitive-data filter is perfect. It is a conservative
  best-effort local guard; users are told (in Urdu) not to translate secrets.
- We **do not** defend against a fully compromised/rooted device or a malicious OS.
- We **do not** guarantee reading/insertion on every app — see `FEASIBILITY.md`.

## 5. Abuse cases we deliberately design against

- The app must be **impossible to use** as a background surveillance tool: no
  background capture, allowlist-only, user-initiated only, visible active
  indicator, one-tap Pause.
- The backend must be **useless** as a free AI proxy for outsiders: App Check +
  rate limits + size limits.
- The AI must be **unable to be steered** by a hostile client message into leaking
  or acting: data-not-instructions framing + strict schema.
