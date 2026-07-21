# Testing Strategy

**Phase 0 deliverable (plan).** What we test and how. Tests are written alongside
each phase; this is the map.

---

## 1. Unit tests

Input normalisation; sensitive-data detection (positive + negative + edge cases);
package allowlisting; AI JSON parsing (valid, malformed, unknown fields, over-long);
reply length limits; UI state transitions; timeout handling; prompt-injection
samples (message content that tries to issue commands); redaction logic.

## 2. Android (instrumented) tests

Onboarding; permission-explanation screens; accessibility enabled vs disabled
states; translation panel; voice flow; insert confirmation; clipboard fallback;
rotation / process recreation; large-font settings; Urdu layout correctness.

## 3. Accessibility integration tests (against a fake app, not real ones)

Because testing directly against TikTok/IG/FB/Messenger is unstable, we build:
- A local **fake chat screen** with fake incoming-message nodes and a fake editable
  input.
- Tests for **successful and failed** `ACTION_SET_TEXT`.
- Tests **proving Send is never clicked** (assert no `ACTION_CLICK` on
  send/post/like/etc.).

## 4. Security tests

Static analysis; dependency vulnerability scan; secret scanning; cleartext-network
test (assert none allowed); exported-component review; log inspection (assert no
chat content); API abuse tests; oversized-input tests; invalid-JSON tests;
prompt-injection tests; sensitive-data exfiltration tests (assert blocked locally).

## 5. Manual device matrix

At least one Samsung phone; at least one near-stock/Google phone; multiple Android
versions; multiple font sizes; Urdu and English device languages; current versions
of the four supported apps. Results feed `COMPATIBILITY_MATRIX.md`.

## 6. Gates

Each phase ends only when its automated tests pass and its checklist is ticked. The
MVP gate is the Definition of Done in `PRD.md §8` / `FEASIBILITY.md §7`.
