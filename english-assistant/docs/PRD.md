# Product Requirements Document (PRD)

**Phase 0 deliverable.** The agreed definition of what English Assistant is, does,
and must never do. This mirrors the owner's brief and is the reference all later
phases are checked against.

---

## 1. Product summary

English Assistant helps an Urdu-speaking person understand English client messages
in TikTok, Instagram, Facebook and Messenger, and reply in English — **without**
copy-pasting between apps. The user **deliberately** selects a message and taps the
assistant. The app translates the meaning into Urdu, reads it aloud, suggests
**one** English reply (with its Urdu meaning), and inserts it **only after an
explicit tap**. The user always presses Send. The user can also speak Urdu; the app
turns it into reviewed English.

## 2. Primary user

A non-technical, Urdu-speaking small-business person who communicates with
English-speaking clients. Cannot necessarily read English. Owner is an absolute
beginner with no coding knowledge.

## 3. Supported apps (allowlist — single source of truth)

| App | Package |
|-----|---------|
| TikTok | `com.zhiliaoapp.musically` |
| Instagram | `com.instagram.android` |
| Facebook | `com.facebook.katana` |
| Messenger | `com.facebook.orca` |

The AccessibilityService **ignores every app not on this list.** The list lives in
one central place in code (`accessibility/PackageAllowlist.kt`).

## 4. Core user flows

- **Flow 1 — Translate a client message** (select → tap → Urdu meaning → listen →
  one English reply + its Urdu meaning → tap Insert → user sends).
- **Flow 2 — Speak Urdu → English reply** (tap Speak Urdu → mic → recognised Urdu →
  English + Urdu back-translation → tap Insert → user sends).
- **Flow 3 — Text-selection fallback** (Process Text → Share → manual paste box;
  never whole-screen capture).
- **Flow 4 — Insertion fallback** (clipboard only on tap → Urdu paste instructions
  → auto-clear; never place sensitive data).

Full step lists are in the owner's brief and reflected in `DATA_FLOW.md`.

## 5. Functional requirements

| ID | Requirement |
|----|-------------|
| FR-01 | Translate selected/targeted English into simple, natural Urdu. |
| FR-02 | Urdu text-to-speech button for the translation. |
| FR-03 | Generate exactly one safe, polite, context-aware English reply. |
| FR-04 | Urdu meaning/explanation of the suggested reply. |
| FR-05 | Insert the approved reply into the focused field only after an explicit tap. |
| FR-06 | Never trigger Send. |
| FR-07 | Urdu speech input → English. |
| FR-08 | Show recognised Urdu, translated English, and Urdu back-translation before insertion. |
| FR-09 | Support the 4 apps via a package allowlist. |
| FR-10 | Large buttons, minimal screens, clear icons, Urdu labels, spoken guidance. |
| FR-11 | First-run Urdu onboarding tutorial. |
| FR-12 | Test mode (translate/voice) without opening another app. |
| FR-13 | Easy Pause Assistant that immediately stops accessibility processing. |
| FR-14 | Persistent visible indication whenever the service is active. |
| FR-15 | No conversation history by default. |
| FR-16 | Optional "remember recent context": tiny, encrypted, temporary, off by default. |

## 6. Non-functional requirements

- **Usability:** Urdu-first, Urdu script (not Roman Urdu) for primary text, large
  touch targets, no nested menus, optional spoken Urdu guidance, confirmation to
  prevent accidental activation, usable by someone who cannot read English.
- **Performance:** immediate progress feedback; prevent duplicate AI requests;
  cancel stale requests; responsive on mid-range devices; cache no private content.
- **Reliability:** handle missing nodes, empty text, unsupported fields, no
  internet, speech failure, AI timeout/malformed responses, target app
  closing/changing — **never crash because a third-party app changed its UI.**

## 7. What the app must never do

Never press Send/Post/Like/Follow/Buy; never monitor in the background; never
capture unrelated apps; never read passwords/banking/OTP/cards/seed phrases/health
data; never open chats or act without an explicit tap; never store full
conversations by default; never upload without a clear user action and disclosure.

## 8. Definition of Done (MVP)

Listed in `FEASIBILITY.md §7`. In short: deliberate targeting → Urdu meaning →
spoken Urdu → one English reply + its Urdu meaning → insert only on tap → never
send → Urdu speech → reviewed English → local sensitive-data block → no key in APK
→ no cleartext → no chat text in logs → works in test screen → per-app compatibility
documented → tests pass → disclosures prepared.

## 9. Phase-by-phase roadmap

| Phase | Name | Key output | Gate |
|-------|------|-----------|------|
| 0 | Feasibility, policy & architecture | These docs | "Phase 0 complete" checklist |
| 1 | Local Android prototype (no AI) | Urdu UI, onboarding, settings, fake-chat test screen, accessibility skeleton, allowlist, safe read + `ACTION_SET_TEXT`, clipboard fallback, mock translations, tests | "Phase 1 complete" |
| 2 | Urdu speech & TTS | Runtime mic permission, Urdu SpeechRecognizer (on-device where possible), retry flow, Urdu TTS, availability checks, audio cleanup, tests | "Phase 2 complete" |
| 3 | Secure backend & AI | Fastify TS backend, strict schemas, secret handling, rate limiting, App Check design, provider abstraction, 4 endpoints, injection-resistant prompts, redacted logging, tests | "Phase 3 complete" |
| 4 | Connect app to backend | Retrofit API, repository, use cases, ViewModels, loading/timeout/retry/offline states, cancellation, local filter before networking, all flows, tests | "Phase 4 complete" |
| 5 | Supported-app compatibility | Per-app testing + compatibility matrix; no coordinates; never identify Send | "Phase 5 complete" |
| 6 | Security & privacy hardening | Manifest/exported audit, NSC, Keystore, backup exclusions, log review, abuse protection, dep + secret scanning, retention verification, privacy policy + disclosure drafts | "Phase 6 complete" |
| 7 | Release preparation | Signed build instructions, APK/AAB commands, Play Console + Accessibility + Data Safety guidance, listing draft, closed-testing plan, crash reporting excluding content, rollback plan | "Phase 7 complete" |

## 10. Out of scope (v1)

User accounts/logins, iOS, group-chat automation, auto-sending, conversation
archives, ad/analytics SDKs, contact/SMS/call-log access.
