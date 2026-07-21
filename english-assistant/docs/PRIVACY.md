# Privacy

**Phase 0 deliverable.** Privacy-by-design rules and a plain-English draft privacy
policy. The finalised policy is prepared in Phase 6.

---

## 1. Privacy-by-design rules

- No registration or account. No contacts, SMS, or call-log access.
- No notification-listener permission. No broad storage permission.
- No analytics containing message text. No advertising SDK.
- No background screen monitoring. No full-chat storage. No screenshots by default.
- Where the AI provider offers a no-training / opt-out tier, use it so chat content
  is not used for model training.
- Message text is processed only when the user explicitly acts, and only the
  targeted text — never the whole screen.

## 2. What data exists, and for how long

| Data | Where | Lifetime |
|------|-------|----------|
| Selected message text | Device memory only | Duration of the active task; cleared on dismiss |
| Translation / reply / back-translation | Device memory only | Same as above |
| Speech transcript (Urdu) | Device memory only | Same as above |
| Text sent to AI | Transits our backend to the provider over TLS | Not stored by our backend; provider retention per §5 |
| Settings (language, app-lock on/off, etc.) | DataStore on device | Until changed/uninstalled; contains no chat content |
| Optional context window (FR-16) | Encrypted on device | Tiny, temporary, off by default; user-clearable |

## 3. Draft privacy policy (plain English — to finalise in Phase 6)

> **English Assistant — Privacy**
>
> English Assistant helps you understand and reply to English messages. It works
> **only when you tap it**, and it reads **only the message you select** in the
> supported apps (TikTok, Instagram, Facebook, Messenger).
>
> **What we process:** the specific message text you choose to translate, or the
> Urdu you choose to speak. To translate it, this text is sent securely (encrypted)
> to our server and then to an AI translation service. We do **not** store your
> messages on our server, and we do **not** keep a history of your conversations on
> your phone.
>
> **What we never do:** we never send messages for you, never read your other apps,
> never run in the background watching your screen, and never access your
> passwords, banking details, verification codes, or card numbers — the app blocks
> those before anything is sent.
>
> **Your controls:** you can pause or turn off the assistant at any time, and use
> the "Clear Temporary Data" button. The app has no login and collects no account
> information.
>
> **AI service:** translation is performed by a third-party AI provider. We use a
> configuration that does not use your text to train models where the provider
> offers it. (The specific provider and its retention terms are documented here
> before release.)
>
> **Contact:** (owner contact to be added before publication.)

## 4. Data Safety form (Play Console) — direction

- **Data collected:** message text you choose to translate — used only to provide
  translation, transmitted encrypted, not stored by us, not sold, not for ads.
- **Data shared:** with the AI translation provider, solely to perform the
  translation you requested.
- **Security:** encrypted in transit; no chat storage.
- Full form completed truthfully in Phase 7 once the provider is fixed.
