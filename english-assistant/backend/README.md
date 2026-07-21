# English Assistant — Secure Backend

**Built in Phase 3.** This folder currently holds only the plan and a secrets
**example** file. No server code exists yet.

## Purpose

Protect the AI provider secret. The AI API key must **never** be inside the Android
app. This small HTTPS service holds the key server-side, validates every request,
and forwards a minimal request to the AI provider.

## Planned stack

- **TypeScript + Node.js + Fastify**, deployed as a small serverless HTTPS API.
- **Accepted alternative:** Firebase Cloud Functions (TypeScript) if it is easier
  for a beginner owner to deploy.

## Planned routes

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/v1/translate-message` | English message → Urdu meaning + intent |
| POST | `/v1/suggest-reply` | Context → exactly one safe English reply |
| POST | `/v1/translate-urdu-speech-text` | Urdu speech text → polite English |
| POST | `/v1/back-translate-reply` | English reply → Urdu meaning |
| GET | `/health` | Liveness check (no data) |

## Planned protections (see `../docs/SECURITY.md`)

Firebase App Check + Play Integrity; per-install anonymous id; rate limiting;
request-size limits; abuse detection; strict content-type enforcement; schema
validation; server-side secret management; **no message-body logging**; redacted
operational logs; secure headers; tightly restricted/disabled CORS; dependency
lockfiles + scanning.

## Secrets

- Real keys are configured only in the deployment environment's secret manager.
- `.env.example` in this folder contains **placeholders only** — never a real key.
- The beginner-safe, step-by-step deploy guide is written in Phase 3.
