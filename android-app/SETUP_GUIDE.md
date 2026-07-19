# English Assistant — Setup Guide (for Uncle's phone)

An Android app that helps read English chat messages (WhatsApp, TikTok, Instagram, Facebook),
explains them in Urdu (text + voice), suggests professional English replies, and types the
chosen reply straight into the chat box.

---

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
| 3 | Tap the customer's message from the list | کسٹمر کا پیغام منتخب کریں |
| 4 | Read the Urdu meaning, or tap 🔊 to hear it | مطلب اردو میں پڑھیں یا 🔊 سے سنیں |
| 5 | Tap one of the 2 suggested English replies — it is typed into the chat box automatically | تجویز کردہ جواب پر ٹیپ کریں — خود لکھا جائے گا |
| 6 | Press **Send** | Send دبائیں |

**To say something in his own words:** tap **🎤 اردو میں بولیں**, speak in Urdu,
the app shows the English translation → tap **✍️ چیٹ میں لکھیں** → press Send.

**To move the bubble:** drag it. **To close the panel:** tap ✕.

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
