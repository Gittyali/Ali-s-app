# English Assistant — Setup Guide (for Uncle's phone)

An Android app that helps read English chat messages (WhatsApp, TikTok, Instagram, Facebook),
explains them in Urdu (text + voice), suggests professional English replies, and types the
chosen reply straight into the chat box.

---

## How translation works (important)

- **Translating messages (and replies) English↔Urdu is done offline, on the phone** — no API, no quota, no error. The first time, it downloads a ~30MB Urdu language pack (needs internet once); after that it works instantly, even offline.
- **The AI (Gemini) is used ONLY to suggest the 2 replies.** If the free AI quota is ever hit (error 429), translation and understanding keep working — only the auto-suggested replies pause, and uncle can still record his own reply.

## Part 1 — Get a free Gemini API key (do this once, on any device)

1. Go to **https://aistudio.google.com** and sign in with a Google account.
2. Click **Get API key** → **Create API key**.
3. Copy the key (a long text starting with `AIza…`). Keep it — you'll paste it into the app.

The free tier is enough for one person's daily chatting. **$0/month.**

## Part 2 — Install the app on the phone

1. On the phone, open this repository's **Releases** page:
   `https://github.com/gittyali/ali-s-app/releases/tag/app-latest`
2. Download **EnglishAssistant.apk**.
3. Open the downloaded file. If the phone says "blocked", tap **Settings → Allow from this source**, then install.
   (This is normal for apps installed outside the Play Store.)

## Part 3 — One-time setup inside the app

Open **English Assistant** and follow the 3 numbered steps on screen:

1. **API key** — paste the Gemini key, tap **Save**, then **Test key** (should show ✅).
2. **Microphone** — tap the button and allow (needed for speaking replies in Urdu).
3. **Accessibility** — tap the button, find **English Assistant** in the list, turn it **ON**, and allow.
   The green 💬 bubble appears on screen.

### Extra step for Oppo / Vivo / Realme / Infinix / Tecno phones (important!)

These phones kill background apps, which makes the bubble disappear. Do both:

- **Settings → Battery → English Assistant → No restrictions / Don't optimize**
- Open recent apps, find English Assistant's card, and **tap the lock 🔒** so the system never closes it.
- If the phone has an **Autostart / Auto-launch** setting, enable it for English Assistant.

---

## How Uncle uses it (daily)

| Step | What he does | اردو |
|---|---|---|
| 1 | Open any chat (WhatsApp / TikTok / Instagram / Facebook) | کوئی بھی چیٹ کھولیں |
| 2 | Tap the green 💬 bubble | سبز 💬 بٹن دبائیں |
| 3 | Tap the customer's message (the list shows customer messages only, newest first) | کسٹمر کا پیغام منتخب کریں |
| 4 | Read the Urdu translation (instant, offline), or tap 🔊 to hear it | اردو ترجمہ پڑھیں یا 🔊 سے سنیں |
| 5 | Each suggested reply shows its Urdu meaning (read it), a 🔊 to hear it, and ✍️ Type to put it in the chat box | ہر جواب کا اردو مطلب لکھا ہوتا ہے، 🔊 سے سنیں، ✍️ سے چیٹ میں لکھیں |
| 6 | Press **Send** | Send دبائیں |

**To say something in his own words:** tap **🎤 اردو میں بولیں**, speak in Urdu,
the app shows the English translation → tap **✍️ چیٹ میں لکھیں** → press Send.

**To move the bubble:** drag it. **To close the panel:** tap ✕.

---

## Security & Privacy — how the app protects you

| Protection | How it works |
|---|---|
| **Cannot see other apps** | The assistant is locked (at the Android system level) to chat apps only: WhatsApp, WhatsApp Business, TikTok, Instagram, Messenger, Facebook, Telegram, imo. Banking apps, JazzCash/Easypaisa, documents, gallery, settings — invisible to it. Tapping the bubble anywhere else shows a 🔒 "Protected" notice. |
| **Sensitive numbers never leave the phone** | Before a message is sent to the AI, the app removes payment-card numbers (checksum-verified), bank account/IBAN numbers, CNIC numbers, and any 14+ digit number, replacing them with placeholders. You'll see "🔒 Sensitive numbers were hidden" when this happens. |
| **Card & financial data is blocked** | If a tapped message contains a card number (any 13–19 digit sequence), CVV/CVC, an expiry date, an IBAN, or a CNIC number, the app refuses to send it and shows a 🔒 notice. It does not even try to translate it. |
| **OTP / password messages are blocked** | If a tapped message looks like an OTP or password message, the app refuses to send it anywhere and shows a security notice. |
| **Pause / resume switch** | The bubble can be turned off anytime — long-press the bubble, or use the ON/OFF button at the top of the app. When off, the assistant is not on screen and reads nothing. Turn it back on from the same button. |
| **Auto-off when screen is off** | When the phone screen turns off, the bubble disappears and the app reads nothing. When the phone wakes/unlocks, the bubble comes back automatically (no re-setup). |
| **No storage, no history** | Messages are never saved, logged, or stored. Only the single message you tap is sent — over HTTPS, only to Google's Gemini API — used for that one answer. |
| **Minimal permissions** | The app has only Internet + Microphone. It has NO permission for contacts, files, photos, SMS, or call logs — Android physically prevents it from reading them. |
| **No cleartext traffic** | All network traffic is HTTPS-only, enforced in the app configuration. |

**Honest limits you should know:** the one message you tap (after scrubbing) does go to Google's Gemini API to be translated — that's how the AI works. Google's free tier may use API data to improve their services. So the rule for uncle is simple: use it for normal customer chat, and never tap it on something truly secret. The app blocks the dangerous categories automatically, but no app can make sending text to the internet 100% risk-free.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bubble disappeared | The phone killed the service — redo the battery steps above, then toggle the Accessibility service off/on. |
| "No messages found" | Open the chat first so messages are visible on screen, then tap the bubble. |
| Reply not typed into chat box | Some apps block direct typing. The reply is copied automatically — long-press the chat box and tap **Paste**. |
| 🔊 doesn't speak Urdu | Phone Settings → search "Text-to-speech" → Google TTS → install the **Urdu** voice. |
| "API error" | Check internet; check the key with **Test key** in the app. |
| Voice input doesn't understand | Speak clearly in Urdu; make sure Google app is installed and updated. |
