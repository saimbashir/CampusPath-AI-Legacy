# Verification record — 10 October 2026

Environment: Python 3.12.14, Linux, SQLite. This record describes checks actually executed for release 0.4.0.

## Executed

- **94 Python tests passed** in the final full run (`python -m pytest -q`, 44.71 seconds). One Starlette/httpx compatibility deprecation warning did not affect results.
- Authentication/privacy coverage: unauthenticated access, student isolation, teacher course boundaries, invitation expiry/revocation/limits, registration rollback, privilege escalation, CSRF, logout/expiry/reset/password-change revocation, inactive accounts, co-teacher grant/removal, private resources and explicitly submitted attachment downloads.
- Learning/workflow coverage: the original A* journey, answer replay and ownership, concurrent answer claim, expiration, course/enrollment, prerequisite validation, question review, adaptive difficulty, exact mock distributions/shortages, delayed feedback, early finish/unanswered marks, hint/repetition discount, six readiness factors, saved plans, completion/archive/rescheduling capacity, notifications, assignments and grade locks.
- Viva coverage: sequential saved turns, cross-user/course denial, no offline AI score or automatic mastery, teacher-confirmed score, one-time review and saved progress/history.
- Voice transport coverage: origin/auth/course/CSRF rejection, sample-rate and malformed/empty-frame rejection, concurrent socket rejection, session revocation, PCM/WAV contract, energy VAD, transcript forwarding and active-session cleanup. Speech-provider calls are replaced with controlled responses in these tests.
- Atomic rate-budget test: 20 concurrent attempts with a budget of 5 accepted exactly 5 and rejected 15. The two-request answer test accepted exactly one answer. These are targeted checks, not sustained load certification.
- Request-size enforcement rejected a chunked oversized body without relying on Content-Length.
- Startup/migrations: fresh copied-source setup, idempotent second launch, retained edits, usable SQLite backup, populated frozen-v1 upgrade, integrity/foreign-key checks, downgrade and re-upgrade. No application server was started by these checks.
- Provider contract/fallback tests cover schema validation, authorized citations, draft-only generation, curriculum rollback, vector authorization/post-filtering, invalid embeddings, unavailable speech and audio-only provider forwarding.
- Actual Tesseract OCR was exercised on printed text. It does not establish handwriting or diagram accuracy.
- **68 DOM/API integration checks passed**. jsdom executed the real UI with fetch bridged to FastAPI TestClient and a fresh migrated/seeded SQLite database. Checks included all three role workspaces and real form/click flows for exams, saved results, planning/rescheduling, viva submission/review, notification reading, assignment submission/grading, profile saving, research retrieval and HTML escaping. No HTTP preview server was used.
- All three application JavaScript files passed `node --check`; Python app/scripts/migrations/launcher compiled successfully.

## Release 0.3 acceptance additions

- Four unrelated subjects (Artificial Intelligence, Linear Algebra, Computer Networks and Environmental Science) pass runtime course creation, material upload, curriculum extraction/approval, chapter-scoped tutor retrieval, assigned viva, generated PCM → controlled STT → editable transcript → structured evaluation → teacher-confirmed marks → analytics/notification checks.
- Environmental Science also passes provider-contract MCQ drafting, source retention, teacher approval, strict material-only delivery and student answer grading.
- Actual included networking PDFs pass upload/extraction, page/chapter restriction and five-question/25-mark generation. Both PDFs were rendered and visually inspected for readable content; this is document QA, not application browser QA.
- Follow-up context, hidden delayed feedback, no double-counted marks, invalid citations, unsupported generated questions, changed-type regeneration rejection, private/cross-course denial, exact fractional allocation, flags, one-time finalization, explicit automatic policy, availability and strict assignment links are covered.
- A 35-excerpt structure test confirms every selected excerpt is processed. Fresh setup and upgrade checks reach migration 0003_universal_viva.
- Concurrent test suites exposed a sample-deck file race during demo seeding; setup now creates its deck in memory. Final backend and UI suites passed while running concurrently against their separate databases.
- The 68 DOM/API checks include formal viva authoring, approval/publication, student answers, teacher-confirmed 8.5/10 results and 85% analytics. Live speech and AI responses remain controlled test doubles; no real external model or microphone is claimed.

## Release 0.4 checks

The final full suite passed 94 tests in 44.71 seconds. New coverage verifies gradual positive mastery updates, repeated assessment with a small bank staying below 80%, eight demo questions per topic, detailed wrong-answer feedback, immediate retrieval after teacher upload, material-derived GBFS abbreviation matching and provider-grounded batch creation with approval/duplicate guards. A focused provider/release suite was rerun after final retrieval and option-validation changes.

The existing 68 DOM/API checks passed. Six additional jsdom viva playback lifecycle checks passed: browser playback, microphone remaining off before completion, opt-in activation after completion, failure leaving the microphone off, provider failure falling back to browser speech, and cancellation preventing stale activation. Browser/provider outputs in this test are doubles. Run `node tests/ui/voice-check.cjs` with jsdom installed to reproduce. Actual rendered layout, microphone hardware and external providers still need device acceptance.

## Reproduce

```bash
python -m pytest -q
node --check app/static/app.js
node --check app/static/workflows.js
node --check app/static/universal.js
cd tests/ui
npm install
node integration.cjs
```

Activate the project's Python environment first. If `python` points elsewhere, set `CAMPUSPATH_TEST_PYTHON` to the full virtual-environment Python executable for the integration command. Node/jsdom are optional QA dependencies, not required to run CampusPath. `dom-check.cjs` remains an additional fixture-rendering check; run `export_fixtures.py` against a seeded demo database first.

The small lexical retrieval smoke benchmark from the prior release remains in `retrieval_benchmark.json`; it is not a representative retrieval-quality study.

## Not executed

Actual rendered browser/screenshots, viewport/Android inspection, microphone/playback hardware, screen-reader/contrast audit, Windows batch launch, live LLM/STT/TTS/embedding/Qdrant/SMTP services, PostgreSQL integration, Docker build/run, hosted deployment, sustained distributed load, independent security review and a faculty usability trial. Browser tooling was unavailable; no screenshots or visual approval were fabricated. These boundaries prevent a production-ready claim.

## Release 0.4.1 validation

After the design/viva refinement, the focused release and universal-viva suite passed 23 tests, the existing DOM/API suite passed 68 checks, and the browser/provider-double playback suite passed six checks. The full 94-test run documented above belongs to 0.4; it was not repeated for this scoped patch. JavaScript syntax checks passed. Added regression coverage verifies that an identical follow-up advances the session while preserving the evaluation. Rendered desktop/mobile and actual voice-provider testing remain pending. The attached voice messages were not transcribed; no fix is attributed to their unknown contents.
