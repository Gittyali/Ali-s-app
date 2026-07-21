# Feasibility, Platform Limits & Google Play Policy Review

**Phase 0 deliverable.** This is the honest technical and policy assessment that
must be understood *before* any code is written.

---

## 1. Plain-English summary of the app

English Assistant is an Android **accessibility + translation helper**. While the
user is inside a supported chat app (TikTok, Instagram, Facebook, Messenger), the
user **deliberately** selects an English message and taps our button. The app:

- reads **only** the text the user targeted (never the whole screen, never in the
  background),
- screens it locally for sensitive data (passwords, OTPs, card numbers…),
- translates the meaning into natural Urdu and can read it aloud,
- suggests **one** polite English reply and shows its Urdu meaning,
- inserts that reply into the chat box **only after the user taps Insert**.

The user can also speak Urdu; the app converts it to English and inserts it after
confirmation. **The user always presses Send themselves.**

---

## 2. Feasibility verdict

**Feasible, with important and unavoidable caveats.** The core idea works using
Android's `AccessibilityService` (to read a selected node and to set text into an
editable field), `SpeechRecognizer` (Urdu speech → text), `TextToSpeech` (Urdu
audio), and a secure backend proxy for AI. **However, behaviour will vary from app
to app and can break when those apps update.** This is a genuine engineering and
policy risk, not a detail. We build graceful fallbacks for every failure.

We will **not** promise that every message or text field in TikTok, Instagram,
Facebook, or Messenger is reliably readable or writable. It is not.

---

## 3. What Android *can* reliably do

- Run an `AccessibilityService` that receives events **only** from an allowlisted
  set of packages, and only while the service is enabled by the user.
- Read the text of an accessibility node that the user has **selected** or that
  currently holds **accessibility focus**, when the target app exposes that text
  as a standard node.
- Detect that a field is a **password** field (`isPassword`) and skip it.
- Insert text into a **focused editable** node using `ACTION_SET_TEXT`, when the
  app implements a standard editable node.
- Fall back to the **clipboard**, Android **Process Text** menu action, and a
  **Share** target when direct access is unavailable.
- Convert Urdu speech to text and speak Urdu aloud **when the device has the
  matching Urdu language pack** installed.

## 4. What Android *cannot* reliably do (honest limits)

- **No guarantee of universal readability.** Third-party apps expose different
  accessibility information. Some text is drawn as a custom-rendered surface (a
  `Canvas`, `SurfaceView`, or image) with **no readable node**. TikTok in
  particular renders a lot of content in non-standard ways.
- **No guarantee of text insertion.** Some apps use custom input fields that do
  not honour `ACTION_SET_TEXT`, or actively reject programmatic text changes.
- **No stability across updates.** When TikTok/IG/FB/Messenger ship an update,
  their internal view structure can change and previously-working reading or
  insertion can stop working. We cannot prevent this; we detect it and fall back.
- **No reliable "the message the user touched".** Accessibility does not hand us a
  clean "user tapped this exact bubble" signal in every app. We approximate it via
  text selection, accessibility focus, and the most-recently-focused node, and we
  fail gracefully when we cannot.
- **We deliberately will not** traverse the whole window to "find" the message,
  because that is both a privacy violation and a policy violation.

**Bottom line for the owner:** In some apps and some screens it will "just work."
In others, the app will politely tell you (in Urdu) that it could not read the
message, and offer the paste box or the copy-and-paste fallback. That is expected
behaviour, not a bug.

---

## 5. Google Play policy risk assessment (important)

`AccessibilityService` is one of the **most scrutinised** capabilities on Google
Play. The relevant policies:

- **Accessibility API must be used for accessibility**, or for a clearly
  disclosed, user-initiated purpose. Helping a user who cannot read English
  understand and reply to messages **is** an assistive use, but Google reviews it
  case by case.
- **Prominent disclosure + consent** is mandatory *before* sending the user to
  Accessibility Settings, explaining what data is accessed and why (we provide an
  Urdu disclosure — see `ACCESSIBILITY_POLICY.md`).
- **No autonomous or deceptive actions.** We never click Send/Post/Like/Buy,
  never act without an explicit tap, never imitate another app's UI.
- **Data minimisation.** We read only user-selected text, never the whole screen,
  never in the background.
- **Play Console declaration.** We must complete the *Accessibility* and *Data
  Safety* declarations truthfully and may need to submit a demonstration video.

**Risk level: HIGH but manageable.** Apps using `AccessibilityService` for
non-accessibility automation are frequently rejected or removed. Our mitigations:
strictly user-initiated design, minimal data, honest disclosure, no autonomous
actions, and a clear assistive purpose for a disadvantaged (non-English-reading)
user. **We cannot and do not promise Google will approve it.** Compliance must be
re-reviewed before publication (Phase 7). A sideloadable APK for the owner's
personal use is a guaranteed fallback if store approval is refused.

---

## 6. Recommended interaction model

**Always user-initiated, never autonomous.** Every action requires a fresh,
explicit tap:

- Trigger = user taps a small **movable floating button** (or uses the Android
  **accessibility shortcut / accessibility button** where available — preferred
  because it avoids the `SYSTEM_ALERT_WINDOW` overlay permission).
- The app reads **one** targeted node, screens it, translates, and shows a panel.
- Insertion requires **another** explicit tap on "Insert English reply."
- A visible, persistent indicator shows whenever the service is active, plus an
  always-available **Pause Assistant** control.

We will start with the **accessibility button/shortcut** approach and only add a
floating overlay if testing shows it is genuinely needed, because the overlay
permission adds policy and UX cost.

---

## 7. Definition of the MVP

The MVP is complete when, on at least one supported app and the built-in test
screen:

1. The user can deliberately target an English message.
2. The app shows understandable Urdu meaning and can speak it aloud.
3. The app produces exactly **one** English reply and shows its Urdu meaning.
4. The reply is inserted **only after an explicit tap**; the app never sends.
5. Urdu speech is converted to reviewed English and inserted the same way.
6. Sensitive text is blocked **locally** before any network call.
7. No AI key is in the APK; cleartext traffic is disabled; no chat text is logged.
8. Fallbacks (Process Text / Share / paste box / clipboard-insert) work.
9. Automated and manual tests pass; disclosures and privacy policy are prepared.

---

## 8. Assumptions

1. The owner will run the app on a normal, unlocked, non-rooted Android phone
   (API 26 / Android 8.0 or newer).
2. The owner (or a helper) can install one Android build tool set once, with our
   exact step-by-step commands. No prior coding knowledge is assumed.
3. The owner can obtain **one** AI provider API key (e.g. an Anthropic key) and
   place it **on the server only**, never in the app. We will give exact steps.
4. A small always-on HTTPS backend (serverless function) is acceptable and its
   modest cost is understood.
5. Urdu speech-to-text and Urdu text-to-speech depend on the phone having the
   Urdu language pack; the app detects this and guides the user to install it.
6. Target apps' accessibility behaviour is outside our control and may change.
7. The owner accepts that Google Play approval for `AccessibilityService` is not
   guaranteed, and that personal sideloading is the fallback.

## 9. Key risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | A target app exposes no readable node for the message | High | Med | Process Text / Share / paste-box fallback + Urdu explanation |
| R2 | `ACTION_SET_TEXT` rejected by a target app | Med | Med | Clipboard-insert fallback with Urdu paste instructions |
| R3 | App update breaks reading/insertion | High (over time) | Med | No hardcoded coordinates; detect failure and fall back; compatibility matrix |
| R4 | Google Play rejects the AccessibilityService | Med–High | High | Honest disclosure, minimal data, assistive purpose; sideload fallback |
| R5 | Sensitive data leaks to AI | Low | High | Local pre-filter + password-node metadata + server validation |
| R6 | AI key leaks | Low | High | Key only on server; App Check / Play Integrity; no key in APK |
| R7 | AI returns unsafe/invented content | Med | Med | Strict JSON schema, server + client validation, "never invent facts" prompt |
| R8 | Urdu language pack missing on device | Med | Low | Detect and guide install; text-only fallback |

---

## ✅ Phase 0 complete — checklist

- [x] Plain-English summary of the app
- [x] Feasibility verdict
- [x] What Android can and cannot reliably do (honest limits)
- [x] Google Play `AccessibilityService` policy risk assessment
- [x] Recommended user-initiated interaction model
- [x] Definition of the MVP
- [x] Threat model → see [`THREAT_MODEL.md`](THREAT_MODEL.md)
- [x] Data-flow diagram (Mermaid) → see [`DATA_FLOW.md`](DATA_FLOW.md)
- [x] Architecture diagram (Mermaid) → see [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [x] Permission matrix → see [`PERMISSIONS.md`](PERMISSIONS.md)
- [x] Package / project structure → see [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [x] Phase-by-phase roadmap → see [`PRD.md`](PRD.md)
- [x] Assumptions and risks (above)
- [x] Explicit statement of what cannot be guaranteed across third-party apps
