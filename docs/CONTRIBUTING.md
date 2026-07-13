# Contributing

Thank you for considering a contribution!

## Ground rules

- Be respectful in issues and reviews.
- One logical change per pull request.
- All code must follow the standards in
  [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — PEP 8, full type hints,
  documented modules, no placeholder code, graceful error handling.
- New behaviour needs tests; changed behaviour needs updated tests.
- The application must never crash on user input — errors surface as
  readable messages.

## Workflow

1. **Open an issue first** for anything larger than a small fix, so the
   approach can be discussed before you invest time.
2. Fork and create a feature branch: `git checkout -b feature/short-name`.
3. Make your change, keeping commits focused with descriptive messages.
4. Run the test suite:
   ```bash
   QT_QPA_PLATFORM=offscreen python -m pytest tests -v
   ```
5. Manually verify the affected flow in the running app when the change
   touches the UI, OCR, speech or export paths.
6. Open a pull request describing **what** changed and **why**, with
   screenshots for UI changes.

## Good first contributions

- Additional OCR engine or AI vision provider integrations
  (see "Extending" in [ARCHITECTURE.md](ARCHITECTURE.md))
- More voice command phrases/languages in `app/speech/commands.py`
- Layout-heuristic improvements with test cases in `tests/test_layout.py`
- Translations of the UI strings

## Reporting bugs

Please include:

- Steps to reproduce, expected vs. actual behaviour
- The log file: `%APPDATA%\AIDocumentAssistant\logs\app.log`
- OS, Python version, and which OCR/AI/speech backends are configured

## Security

Do not open public issues for security-sensitive reports (e.g. anything
involving API-key handling); contact the maintainers privately instead.
