# Permission Matrix

**Phase 0 deliverable.** Every permission / special access the app will use — its
purpose, *when* it is requested, the fallback if denied, and its risk.

## Permissions we WILL use

| Permission / access | Purpose (plain English) | When requested | If denied — fallback | Risk / notes |
|--------------------|--------------------------|----------------|----------------------|--------------|
| `INTERNET` | Talk to our secure backend for translation. | Install (normal permission, no prompt). | App works only in offline/test paths; shows "no internet" Urdu message. | Low. Standard. |
| `BIND_ACCESSIBILITY_SERVICE` (declared on the service) | Read the message the user selected; insert an approved reply. | User is guided to Accessibility Settings **after** an Urdu prominent-disclosure + explicit consent. | Fallbacks: Process Text, Share, paste box, clipboard insert. | **High scrutiny.** Core to the app; used minimally and only in allowlisted apps. See `ACCESSIBILITY_POLICY.md`. |
| `RECORD_AUDIO` | Convert spoken Urdu to text. | **Only** the first time the user taps "Speak Urdu" (runtime prompt at that moment). | Voice feature disabled; typing/translation still work; Urdu message shown. | Med. Requested late, per feature, never background. |
| `POST_NOTIFICATIONS` | Show the persistent "assistant active" indicator on Android 13+. | First time the foreground indicator is shown, on Android 13+ only. | Indicator via other means; feature still functions. | Low. |

## Special access (not a normal permission)

| Access | Purpose | When | Fallback | Risk |
|--------|---------|------|----------|------|
| `SYSTEM_ALERT_WINDOW` (overlay) — **only if needed** | A movable floating assistant button. | Requested **separately**, with its own Urdu explanation, **only if** the accessibility-button/shortcut approach proves insufficient in testing. | Use Android's accessibility button / accessibility shortcut instead (preferred; no overlay). | Med. Adds policy + UX cost; we avoid it unless required. |

## Package visibility

| Element | Purpose |
|---------|---------|
| `<queries>` for the 4 supported packages only | Lets the app recognise supported apps without requesting broad package visibility. **We never use `QUERY_ALL_PACKAGES`.** |

## Permissions we will explicitly NOT request

`READ_SMS`, `RECEIVE_SMS`, `READ_CONTACTS`, `READ_CALL_LOG`, `QUERY_ALL_PACKAGES`,
broad storage (`READ/WRITE_EXTERNAL_STORAGE`, `MANAGE_EXTERNAL_STORAGE`),
`BIND_NOTIFICATION_LISTENER_SERVICE`, camera, location, device-admin,
`READ_PHONE_STATE`, and any advertising/analytics identifier.

## Timing principle

Every sensitive access is **just-in-time** and tied to a concrete user action:
- Accessibility → only after the Urdu disclosure + consent.
- Microphone → only on first "Speak Urdu" tap.
- Overlay → only if chosen, and only with its own explanation.

Nothing sensitive is requested at first launch beyond what onboarding explains.
