# Installation Guide

## 1. Prerequisites

- **Windows 10 or 11** (Linux/macOS also work for development)
- **Python 3.10 or newer** — from https://python.org; tick
  *"Add python.exe to PATH"* during setup.

Check your installation:

```powershell
python --version
```

## 2. Get the code and core dependencies

```powershell
git clone <this-repository>
cd Ali-s-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

This installs the UI framework, imaging, PDF import and DOCX export.
The application now starts:

```powershell
python main.py
```

Everything below is optional and enables specific features.

## 3. OCR engine (needed for "Read Current Page" without an AI provider)

Install **one** of the following.

### Option A — Tesseract (recommended, lightest)

1. `pip install pytesseract` (already in requirements.txt)
2. Install the Windows binary from
   https://github.com/UB-Mannheim/tesseract/wiki
3. During setup, select additional language data if needed (e.g. **Urdu**).
4. If you did not add it to PATH, set the full path to `tesseract.exe`
   in **Settings → OCR → Tesseract path**
   (typically `C:\Program Files\Tesseract-OCR\tesseract.exe`).
5. Language examples for **Settings → OCR → Languages**: `eng`, `urd`,
   `eng+urd`.

### Option B — EasyOCR

```powershell
pip install easyocr
```

Large download (PyTorch); no extra binary needed. Languages: `en`, `ur`
(comma-separated).

### Option C — PaddleOCR

```powershell
pip install paddlepaddle paddleocr
```

Languages: single code, e.g. `en` (Urdu script is covered by the Arabic
models: `ar`).

## 4. AI vision provider (optional, best reading quality)

Open **Settings → AI Provider**, choose a provider and paste your API key:

| Provider | Key from                       | Default model      |
|----------|--------------------------------|--------------------|
| Claude Vision (Anthropic) | console.anthropic.com | claude-sonnet-5 |
| OpenAI Vision | platform.openai.com        | gpt-4o             |
| Gemini Vision (Google) | aistudio.google.com  | gemini-2.0-flash   |
| Local Vision Model | — (no key)               | llava              |

For **local models**, run an OpenAI-compatible server such as
[Ollama](https://ollama.com) (`ollama pull llava`, endpoint
`http://localhost:11434/v1`) or LM Studio, and set the endpoint in Settings.

With a provider configured, *Read Current Page* sends the page image (plus
the raw OCR text as a hint) to the model and reconstructs the document
structure. Without one, the app falls back to OCR layout analysis.

## 5. Voice dictation (optional)

1. Install the audio + recognition packages (already in requirements.txt):

   ```powershell
   pip install sounddevice vosk
   ```

2. Download a **Vosk model** for your dictation language from
   https://alphacephei.com/vosk/models and extract it anywhere:
   - English: `vosk-model-small-en-us-0.15` (~40 MB) or the large model
   - Urdu: use a Vosk-compatible Urdu model if available
   - Roman Urdu: works well with an **English** model
3. Point **Settings → Speech → Vosk model folder** at the extracted folder.
4. Pick your microphone in **Settings → Speech** and press
   **Start Dictation** (Ctrl+D).

## 6. Verifying the installation

Run the unit tests:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests -q
```

All tests should pass. Then start the app (`python main.py`), create a
project, import an image and press **Read Current Page**.

## Troubleshooting

- **"No OCR engine is installed"** — complete step 3, or configure an AI
  provider (step 4).
- **"The Tesseract binary was not found"** — set the path in
  Settings → OCR, or add the install folder to PATH.
- **"Could not open the microphone"** — close other apps holding the mic;
  check Windows microphone privacy settings.
- **Logs** — every run writes detailed logs to
  `%APPDATA%\AIDocumentAssistant\logs\app.log`; attach that file to bug
  reports.
