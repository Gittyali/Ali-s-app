# Developer Guide

## Setting up

```bash
git clone <this-repository>
cd Ali-s-app
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pytest
```

Run the app with `python main.py`; run the tests with:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests -v
```

(`offscreen` lets Qt-dependent tests run without a display — required on CI
and headless machines, harmless elsewhere.)

## Code standards

- **PEP 8**, 4-space indentation, ~88 character lines.
- **Type hints everywhere** — public functions, methods and attributes.
- `from __future__ import annotations` at the top of every module.
- Every module starts with a docstring explaining its role; public classes
  and non-trivial methods carry docstrings.
- Logging via `logging.getLogger(__name__)`; never `print`.
- User-facing failures raise the package's typed error with a message that
  can be shown in a dialog verbatim; programming errors may raise anything.

## Threading rules (important)

1. Widgets and `QPixmap` are **UI-thread only**. Worker code may use
   `QImage`, PIL, and pure Python.
2. Long work goes through `app.utils.workers.run_in_background`; results
   come back as queued signals on the UI thread.
3. Do not create/destroy `QObject`s across threads. Workers are kept alive
   by the `_active_workers` registry until their `finished` signal has been
   delivered — do not "simplify" this away; it prevents a real crash.
4. The dictation loop runs on its own `QThread` (continuous, not pooled).

## Where things live

| Task | Location |
|------|----------|
| Add a setting | `app/settings/settings_manager.py` (+ dialog tab) |
| Add a toolbar action / shortcut | `app/ui/main_window.py`, defaults in settings |
| Change heading sizes / list styles | `app/formatting/rich_text.py` |
| Tune OCR layout heuristics | `app/ocr/layout.py` (constants at top) |
| Change the AI prompt contract | `app/vision/prompts.py` + `app/formatting/markdown_parser.py` |
| Add voice command phrases | `app/speech/commands.py` |

## Testing guidance

- Non-UI logic (parsers, layout, project, exporters) is covered by unit
  tests under `tests/`; add tests with any behavioural change.
- Qt-dependent tests take the `qapp` fixture from `tests/conftest.py`.
- For manual end-to-end testing without hardware: the main window's
  dictation handler can be driven directly —
  `window._on_dictation_final("heading hello new paragraph world")`.

## Debugging

- Logs: `%APPDATA%/AIDocumentAssistant/logs/app.log` (DEBUG level).
- `PYTHONFAULTHANDLER=1 python main.py` prints native-crash tracebacks.
- Read-pipeline stages are reported via `AppController.read_progress` and
  appear live in the status bar.

## Release checklist

1. `python -m pytest tests` is green.
2. `python main.py` starts, imports images + a PDF, reads a page with the
   configured OCR engine, exports DOCX and PDF.
3. Bump `__version__` in `app/__init__.py`.
4. Update README/docs if behaviour changed.
