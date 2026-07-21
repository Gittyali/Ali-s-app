# Accessibility Service Policy & Prominent Disclosure

**Phase 0 deliverable.** How we use the AccessibilityService responsibly, and the
Urdu prominent-disclosure the user must see and accept **before** we open
Accessibility Settings. Finalised wording is confirmed in Phase 6.

---

## 1. Scope of accessibility use

- Listen **only** while the assistant is enabled **and** only inside allowlisted
  packages (TikTok, Instagram, Facebook, Messenger).
- Use the **minimum** event types and flags required. Do **not** traverse the whole
  active window after every event.
- Prefer, in order: (1) user-selected text, (2) accessibility focus, (3) the node
  explicitly targeted immediately before the assistant button was activated.

## 2. Text-capture rules

- Ignore password fields and nodes marked `isPassword`.
- Ignore editable fields when the user requests translation of an **incoming**
  message (unless explicitly selected).
- Reject blank, extremely long, hidden, or malformed content; enforce a character
  limit; never concatenate the whole screen; never read notifications.
- Never process content from browsers, banking, password managers, email, crypto,
  payment, gallery, or system settings apps (allowlist already excludes them).
- Clear the captured node reference after completing or cancelling.

## 3. Insertion rules

- Insert only into a **currently focused editable** node, after a **fresh explicit
  Insert tap**, verifying the package is allowlisted and the field is still in the
  same active window.
- Prefer `ACTION_SET_TEXT`; if unsupported, offer explicit clipboard fallback.
- **Never** `ACTION_CLICK` on Send/Submit/Post/Like/Follow/Purchase/Delete/
  navigation buttons. **Never** simulate a sequence of autonomous actions.

## 4. Interface model

Prefer Android's accessibility button / accessibility shortcut. If a floating
overlay (`SYSTEM_ALERT_WINDOW`) is truly needed, request it separately, use it only
for the assistant control, keep it movable and dismissible, show which app is
supported, and never obscure security/permission dialogs or imitate another app.

## 5. Prominent disclosure (shown BEFORE opening Accessibility Settings)

The user must see this in **Urdu** (English shown here for the record) and give
**affirmative consent**. We do not use misleading wording like "required
permission" without explaining scope.

> **English Assistant — before you turn on Accessibility**
>
> - This app can read the text **you deliberately select** in supported chat apps
>   (TikTok, Instagram, Facebook, Messenger). It does not read anything else.
> - It can put a reply into the chat box **only when you tap Insert**.
> - It will **never** send a message for you.
> - The text you choose to translate is sent **securely** to an AI service to
>   translate it.
> - You can **pause or turn off** this access at any time.
> - It will **not** process passwords, banking details, verification codes (OTP),
>   or other sensitive information.
>
> Do you agree to continue and open Accessibility Settings?
> **[ Yes, continue ]   [ No ]**

Urdu draft (to be reviewed by a native speaker in Phase 6):

> **انگلش اسسٹنٹ — ایکسیسبیلٹی آن کرنے سے پہلے**
> - یہ ایپ صرف وہی عبارت پڑھ سکتی ہے جو آپ خود سپورٹڈ چیٹ ایپس (ٹک ٹاک، انسٹاگرام،
>   فیس بک، میسنجر) میں منتخب کرتے ہیں۔ اس کے علاوہ کچھ نہیں پڑھتی۔
> - یہ صرف اُس وقت جواب چیٹ باکس میں ڈالتی ہے جب آپ "Insert" دباتے ہیں۔
> - یہ آپ کی طرف سے کبھی پیغام نہیں بھیجے گی۔
> - ترجمے کے لیے منتخب عبارت محفوظ طریقے سے AI سروس کو بھیجی جاتی ہے۔
> - آپ کسی بھی وقت اس رسائی کو روک یا بند کر سکتے ہیں۔
> - یہ پاس ورڈ، بینک تفصیلات، OTP کوڈ یا دیگر حساس معلومات پر عمل نہیں کرے گی۔

## 6. Play policy compliance notes

- Purpose is **assistive**: helping a user who cannot read English understand and
  reply to messages.
- Strictly **user-initiated**; **no autonomous** actions; **data-minimised**.
- We complete the Play Console Accessibility declaration truthfully and prepare a
  demonstration if requested (Phase 7).
- Approval is **not guaranteed**; personal sideloading is the fallback.
