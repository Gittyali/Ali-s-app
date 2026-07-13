# Architecture

## Layering

```
┌────────────────────────────────────────────────────────┐
│ app/ui        widgets, dialogs, themes (Qt only here)  │
├────────────────────────────────────────────────────────┤
│ app/core      project, pages, autosave, controller     │
├──────────────┬───────────────┬───────────────┬─────────┤
│ app/ocr      │ app/vision    │ app/speech    │ export  │
├──────────────┴───────┬───────┴───────────────┴─────────┤
│ app/document + app/formatting   (neutral doc model)    │
├────────────────────────────────────────────────────────┤
│ app/settings, app/utils         (foundations)          │
└────────────────────────────────────────────────────────┘
```

Rules that keep the graph clean:

- `utils` and `settings` import nothing from other app packages.
- `document` is the neutral hub: recognition (OCR/vision) produces it,
  formatting renders it; neither side knows about the other.
- Engines/providers are registered in per-package factories; the rest of
  the app talks only to abstract interfaces.
- Only `app/ui` touches widgets. `core.controller` communicates through Qt
  signals so it can be exercised headlessly in tests.

## The read pipeline

`MainWindow → AppController.read_page(page_id, PIL image)`:

1. The image is the *processed* view (rotation/brightness/contrast/
   enhancement applied), so the user can visually fix a bad scan before
   reading it.
2. On a thread-pool worker:
   - The configured `OCREngine` recognises geometric text lines.
   - If an AI `VisionProvider` is configured: the image plus OCR text (as a
     hint) is sent to the model, which returns constrained Markdown;
     `formatting.markdown_parser` converts it into a `StructuredDocument`.
   - Otherwise (or if the provider fails): `ocr.layout` reconstructs
     structure from geometry — font-size ratios detect headings, markers
     detect lists, margins detect alignment, vertical gaps split paragraphs.
3. The outcome is emitted back on the UI thread; the editor renders it via
   `formatting.rich_text` **only if that page is still active** — otherwise
   the content is stored directly on its page. Reading never switches pages.

## The batch pipeline (Read All Pages)

`AppController.read_all_pages(list[PageReadSpec])` runs one worker that
loops over the pages **sequentially and in page order**. Each spec carries
the page's stored view adjustments, so the batch reads exactly what the
user would see. Per page it reuses the same `_recognize` core as single
reads and emits the result through the same `read_finished` signal, so
storage and UI handling are shared. A failing page emits
`batch_page_failed` and the loop continues; `cancel_batch()` sets a
`threading.Event` checked between pages, so cancellation takes effect after
the page currently in flight. `batch_finished` delivers a `BatchSummary`
(succeeded/failures/cancelled) that the main window turns into a report
dialog, and an autosave snapshot is flushed immediately after the batch.

## The dictation pipeline

```
sounddevice (PortAudio thread)
  → queue → _DictationWorker loop (QThread)
    → VoskEngine.accept_audio() → partial/final transcripts (signals)
      → MainWindow → VoiceCommandParser
        → text  → DocumentEditor.insert_dictation()
        → command → DocumentEditor.apply_command() / page navigation
```

Partials give live feedback in the status bar; only finals touch the
document. The command parser does longest-match phrase scanning in English,
Urdu script and Roman Urdu, with compound number parsing for
"go to page one hundred twenty five".

## Data model and persistence

- A **project** is a self-contained folder (`Name.adaproj`) with
  `project.json` and a `pages/` directory of imported images (copies).
- A **page** holds the image path, view adjustments, workflow status and
  its document as rich-text HTML (the editor's native serialisation).
- Saves are atomic (temp file + rename). Autosave writes the same JSON to a
  per-project snapshot in the user data directory; on startup a surviving
  snapshot triggers a recovery offer, merging page content by `page_id`.

## Memory strategy (500-page projects)

- Page images live on disk; RAM holds only sidebar thumbnails
  (~120 px, built lazily on the thread pool) and the currently displayed
  page's pixmap.
- Document HTML per page is plain text — negligible.
- Every heavy operation (import, PDF rendering, OCR, AI calls, exports,
  thumbnailing, image adjustment) runs on `QThreadPool` workers; the UI
  thread only paints and reacts to signals.
- Stale-render tokens in the viewer discard superseded background renders
  when the user flips pages quickly.

## Error handling policy

- Backends raise typed errors (`OCREngineNotAvailableError`,
  `VisionProviderError`, `SpeechEngineError`, `ProjectError`) whose
  messages are written for end users and shown in dialogs.
- Background workers catch **all** exceptions, log tracebacks and surface
  the message via an `error` signal — a failed job can never crash the app.
- `sys.excepthook` is replaced to log any uncaught exception.
- Logs rotate in `<user-data>/logs/app.log` (2 MB × 5 files).

## Extending

- **New OCR engine**: subclass `app.ocr.base.OCREngine`, add it to
  `_ENGINE_CLASSES` in `app/ocr/factory.py`.
- **New AI provider**: subclass `app.vision.base.VisionProvider`, register
  it in `app/vision/factory.py` (and add settings fields if needed).
- **New voice command**: add a `CommandType`, phrases in
  `app/speech/commands.py`, and a handler in
  `DocumentEditor.apply_command`.
- **New export format**: add a module to `app/export` that consumes the
  list of per-page HTML strings.
