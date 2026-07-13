# AI Document Assistant

An open-source Windows desktop application that converts scanned pages and
screenshots into editable, Word-like documents — using OCR, AI vision and
voice dictation.

Built with Python and PySide6 (Qt).

## What it does

1. **Import** any number of pages — images (PNG, JPEG, BMP, TIFF), PDFs and
   scanned documents. 1 page or 500; the only limit is system memory.
2. **Read** the selected page with *Read Current Page*: the app runs OCR
   and (optionally) an AI vision model to reconstruct the document —
   headings, subheadings, paragraphs, lists, tables, footnotes, numbers and
   legal citations — not just raw text.
3. **Correct** the result in a rich text editor by keyboard or by voice,
   including live dictation in English, Urdu and Roman Urdu with spoken
   formatting commands ("heading", "bold", "new paragraph", "go to page 15").
4. **Export** the whole project as a DOCX or PDF that keeps the formatting.

## Key principles

- **You are in control of pages.** Imported pages stay permanently in the
  sidebar. The active page changes only when *you* click, press a shortcut
  or say a voice command — the software never switches pages by itself.
- **Pluggable engines.** OCR (Tesseract / EasyOCR / PaddleOCR) and AI vision
  (Claude / OpenAI / Gemini / local models) are interchangeable backends
  behind stable interfaces; the app depends on none of them specifically.
- **Never lose work.** Projects autosave every few minutes and unsaved work
  is offered for recovery after a crash.

## Quick start

```bash
git clone <this-repository>
cd Ali-s-app
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

For OCR you also need at least one engine — the lightest option is
Tesseract; see [docs/INSTALLATION.md](docs/INSTALLATION.md) for the
complete, step-by-step guide (including voice dictation models and AI
provider setup).

## The workflow

```
Import 50 screenshots  →  select Page 1  →  Read Current Page
→  content appears in the editor  →  fix mistakes by voice or keyboard
→  click Page 2  →  repeat  →  Export DOCX / PDF
```

## Voice commands

While dictating, these phrases act as commands instead of text
(English shown; Urdu and Roman Urdu equivalents also work):

| Say                      | Effect                        |
|--------------------------|-------------------------------|
| heading / sub heading    | Turn current line into a heading |
| bold / italic / underline| Toggle inline style           |
| center / left align / right align | Paragraph alignment  |
| bullet list / numbered list | Toggle list mode           |
| new paragraph / next line| Paragraph / line break        |
| insert page break        | Hard page break               |
| next page / previous page| Navigate pages                |
| go to page 15            | Jump to a page (words or digits) |

## Project structure

```
main.py            entry point
app/
  core/            project model, autosave, read-pipeline controller
  ui/              main window, sidebar, image viewer, editor, settings
  ocr/             OCR engine interface + Tesseract/EasyOCR/PaddleOCR
  vision/          AI vision interface + Anthropic/OpenAI/Gemini/local
  speech/          microphone capture, Vosk streaming, voice commands
  document/        neutral structured document model
  formatting/      markdown ⇆ rich text conversion
  export/          DOCX and PDF exporters
  settings/        typed persistent settings
  utils/           logging, paths, imaging, background workers
tests/             unit tests (pytest)
docs/              installation, architecture, developer & contribution guides
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit
together and [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for working
on the code.

## Requirements

- Windows 10/11 (the code is cross-platform; Linux/macOS work for development)
- Python 3.10+
- See `requirements.txt` for packages

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Contributions are welcome; please read
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) first.
