# AI Document Assistant

An open-source Windows desktop application that converts scanned pages and
screenshots into editable, Word-like documents — using OCR, AI vision and
voice dictation.

Built with Python and PySide6 (Qt).

## What it does

1. **Import** any number of pages — images (PNG, JPEG, BMP, TIFF), PDFs and
   scanned documents. 1 page or 500; the only limit is system memory.
2. **Read** the selected page with *Read Current Page*, or the whole
   project with *Read All Pages* (Ctrl+Shift+R): the app runs OCR and
   (optionally) an AI vision model to reconstruct the document — headings,
   subheadings, paragraphs, lists, tables, footnotes, numbers and legal
   citations — not just raw text. Watermarks, highlighter marks and
   decorative underlines are ignored. *Read All Pages* processes pages
   sequentially in order with a progress bar and Cancel button; a failing
   page is skipped and reported while the batch continues.
3. **Correct** the result in a rich text editor by keyboard or by voice,
   including live dictation in English, Urdu and Roman Urdu with spoken
   formatting commands ("heading", "bold", "new paragraph", "go to page 15").
4. **Export** the whole project as a DOCX or PDF that keeps the formatting.

## Key principles

- **You are in control of pages.** Imported pages stay permanently in the
  sidebar. The active page changes only when *you* click, press a shortcut
  or say a voice command — the software never switches pages by itself.
- **Sidebar order is processing order.** Drag pages to reorder them;
  reading and export always follow exactly the order shown. Multi-select
  with Ctrl+Click / Shift+Click / Ctrl+A turns *Read Current Page* into
  *Read Selected Pages (N)*.
- **One document, if you want it.** In Append output mode (the default,
  Settings > Reading) every page you read joins one continuous document in
  the editor — page after page, in order, with optional "— Page N —"
  markers. Switch to Replace mode to keep content on each page separately.
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

Or hands-off:

```
Import 50 screenshots  →  (drag to reorder if needed)  →  Read All Pages
→  watch "Page 3 of 50" progress, Cancel any time
→  one continuous document builds up in the editor
→  review/correct  →  Export DOCX / PDF
```

Reading settings (Settings > Reading): output mode (append/replace), auto
read after import, page separators, continue after error, ignore decorative
underlines, ignore watermarks. Transient API failures (rate limits, network
hiccups) are retried automatically with backoff, and the project is
snapshotted after every completed page so a crash can never lose a batch.

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
