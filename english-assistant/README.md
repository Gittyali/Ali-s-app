# English Assistant (انگلش اسسٹنٹ)

An Android helper that lets an Urdu-speaking person **understand English client
messages** in TikTok, Instagram, Facebook and Messenger, and **reply in
English** — without endlessly copying and pasting text between apps.

> **Status: Phase 0 (feasibility, policy & architecture).**
> No production app code exists yet. This folder currently contains only the
> planning and design documents. Building starts in Phase 1.

---

## What it will do (in plain words)

1. You are chatting with an English-speaking client inside TikTok / Instagram /
   Facebook / Messenger.
2. You **tap or select** the client's English message and then tap the English
   Assistant button. **Nothing happens unless you tap.**
3. The app shows you the **meaning in simple Urdu** and can **read it aloud**.
4. The app suggests **one** polite English reply, and shows you its **Urdu
   meaning** so you know exactly what it says.
5. If you like it, you tap **"Insert English reply"** and the text drops into
   the chat box. **You** press Send yourself — the app never sends anything.
6. You can also **speak in Urdu**; the app turns it into English, shows you both
   versions, and inserts the English after you tap Insert.

## What it will NEVER do

- It never presses **Send**, Post, Like, Follow, Buy, or any other button.
- It never watches your screen in the background or reads other apps.
- It never reads passwords, banking details, OTP / verification codes, card
  numbers, or other sensitive information — those are blocked before anything
  leaves your phone.
- It never stores your conversations by default.
- Your AI translation key is **never** inside the app; a small secure server
  holds it.

---

## Documents in this folder

| File | What it covers |
|------|----------------|
| [`docs/FEASIBILITY.md`](docs/FEASIBILITY.md) | Can Android actually do this? Honest limits. Google Play policy risk. |
| [`docs/PRD.md`](docs/PRD.md) | The full product requirements (what we are building). |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the app is put together (with diagram). |
| [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md) | Exactly how a message travels through the system (with diagram). |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | What could go wrong and how we defend against it. |
| [`docs/PERMISSIONS.md`](docs/PERMISSIONS.md) | Every phone permission, why, when, and the fallback. |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Security rules for the app and the server. |
| [`docs/PRIVACY.md`](docs/PRIVACY.md) | Privacy-by-design rules and a draft privacy policy. |
| [`docs/ACCESSIBILITY_POLICY.md`](docs/ACCESSIBILITY_POLICY.md) | The Urdu "prominent disclosure" and Play policy compliance. |
| [`docs/TESTING.md`](docs/TESTING.md) | How we test everything. |
| [`docs/COMPATIBILITY_MATRIX.md`](docs/COMPATIBILITY_MATRIX.md) | Per-app (TikTok/IG/FB/Messenger) results — filled in Phase 5. |
| [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) | Everything needed before publishing. |
| [`backend/README.md`](backend/README.md) | The secure server (built in Phase 3). |

---

## Roadmap at a glance

| Phase | Name | Output |
|-------|------|--------|
| **0** | Feasibility, policy & architecture | **← you are here** — these docs |
| 1 | Local Android prototype (no AI) | Urdu-first app, onboarding, accessibility skeleton, fake-chat test screen |
| 2 | Urdu speech & text-to-speech | Speak Urdu, listen to Urdu |
| 3 | Secure backend & AI | The translation/reply server |
| 4 | Connect app to backend | Real translations in the app |
| 5 | Supported-app compatibility | Tested against real TikTok/IG/FB/Messenger |
| 6 | Security & privacy hardening | Audits, disclosures, privacy policy |
| 7 | Release preparation | Play Store submission materials |

See [`docs/PRD.md`](docs/PRD.md) for the detailed roadmap.

## Assumptions

See the "Assumptions & Risks" section of [`docs/FEASIBILITY.md`](docs/FEASIBILITY.md).
