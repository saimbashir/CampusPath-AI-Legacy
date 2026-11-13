# CampusPath AI

A Python/FastAPI adaptive learning application with a persistent student knowledge model, prerequisite reasoning, assessment evidence, cited course retrieval and course-scoped teacher analytics.

**Release: 0.5.0 — tested development build. The full master brief is not complete.** Read `FINAL_STATUS.md` before a class presentation or real deployment. This is runnable source, not a static dashboard. It is not yet a production-certified university system.

## New in 0.5.0 — Clearer workspace and personalized viva

- New forest-green visual system, polished light/dark cards, stronger mobile spacing and a shorter main menu with advanced features under **More learning tools**.
- **Student Practice viva defaults to 30 questions**, rotating through 30 question patterns and per-session wording variation. Practice questions are based on teacher-created topics, not falsely advertised as model-generated facts. Reloads and retries preserve each saved session.
- **Formal viva can randomize teacher-approved questions for each student.** To actually give students different question sets, the approved pool must contain **more questions than each student takes** (for example, 45–60 approved for 30 per student). Teachers can generate an additional batch of 10 drafts and must approve supported questions before publication. A pool of only 30 varies order, not content.
- Real LLM generation and meaningful automatic feedback **require provider credentials**; the offline version transparently saves answers for teacher review instead of inventing grades.

Read [the 0.5.0 release guide](docs/RELEASE_0_5_0.md) for the exact flows and limitations.

## Design and viva refinement (0.4.1)

The latest theme uses warm neutral surfaces and forest-green accents, aligned buttons/forms and a clearer responsive viva layout. Exact repeated follow-ups are suppressed; evaluator instructions request focused, source-supported teaching feedback. See docs/RELEASE_0_4_1.md for scope and validation.

## Updated learning experience (0.4)

The interface now defaults to a paper-and-ink light theme with blue accents and a matching dark theme. Topic practice defaults to eight questions. The included demo has eight varied questions per topic; existing unmodified demo courses receive the additional questions idempotently at startup. Teacher courses can generate batches of 4–20 material-grounded MCQ drafts through the question-bank editor, then review/approve each question. A shortage notice identifies smaller banks rather than pretending a two-question check establishes mastery.

Tutor retrieval reads current uploaded excerpts on every request and derives abbreviations from course topic names and capitalized source phrases (including GBFS). Missing evidence asks for relevant teacher material without claiming the whole document is unavailable. Wrong-answer feedback now includes the selected and correct options, deciding explanation, related concept and a self-check; this is available offline from teacher-authored content.

Quiz mastery gains are capped at three percentage points per unassisted correct answer, with repeat/hint discounts. Progress above 79% needs at least 12 distinct questions across three assessments; progress above 89% also needs practice on two dates. Estimates never reach 100%. These are transparent conservative heuristics, not a calibrated psychometric model. Existing saved progress is retained. Quiz score remains distinct from mastery.

Viva question playback falls back from the configured TTS service to browser speech. Opt-in microphone activation follows successful playback only; playback errors leave it off. Configure your LLM and speech services and rehearse on the actual presentation device using docs/UNIVERSAL_VIVA_DEMO.md. No trained model or private provider keys are bundled.

## Quick start

Read **START_HERE.md**. On Windows, double-click **START.bat**; on macOS/Linux, run **sh start.sh**. The launcher installs pinned dependencies, migrates and checks SQLite, seeds a local demo only when appropriate, and preserves existing work. `python run.py --check --backup` performs setup and makes a SQLite backup without launching a server.

## Manual installation (Python 3.12+)

Extract the ZIP and open a terminal inside the `campuspath` folder.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python scripts/seed_demo.py
python -m uvicorn app.main:app --reload
```

If PowerShell blocks activation, use `.venv\Scripts\python.exe` instead of `python` in the remaining commands; changing machine-wide execution policy is unnecessary.

### macOS / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
cp .env.example .env
python -m alembic upgrade head
python scripts/seed_demo.py
python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**. Internet is needed to install packages. After installation, the deterministic demo, lexical retrieval and browser interface work offline. Browser speech recognition may still require an online browser service; typed practice works offline.

## Demo accounts — local synthetic data only

| Role | Email | Password |
|---|---|---|
| Student, Saim Bashir, 23F-1234 | saim@campuspath.demo | CampusPath-Demo!2026 |
| Another student | ahmed@campuspath.demo | CampusPath-Demo!2026 |
| Teacher | teacher@campuspath.demo | CampusPath-Demo!2026 |
| Administrator | admin@campuspath.demo | CampusPath-Demo!2026 |

Enrollment code: `AI-FALL26-DEMO`. Seeded starting mastery values and people are demonstration data. Newly submitted answers, grades and notes are real persisted application records. Do not deploy this seeded database for real users or reuse demo passwords. Seed runs are idempotent for an already-seeded database; they do not reset your work.

## First real course

Use a fresh database with no seeded demo users. Run migrations, then:

```bash
python scripts/manage.py create-admin --email administrator@your-university.example
python scripts/manage.py invite --admin-email administrator@your-university.example --days 7 --uses 1
```

The commands request passwords interactively. The invitation is shown once in the administrator terminal for private delivery; only its digest is stored. It is never returned through an API, template or static JavaScript. A verified teacher registers with that invitation and subsequently logs in with their own email/password. Revoke invitations in the admin interface; rotate by revoking and creating a new invitation.

Teacher → create course section → add/upload course material → edit course concepts → write or generate question drafts → review and approve → share enrollment code. Student → register → join → diagnostic/practice → tutor → revision. Teachers only see enrolled students in their own sections.

## Material-grounded courses and formal viva

Use **Material curriculum** to select teacher-provided files, chapters, pages, units, sections or CLOs. Extract and review concepts with source quotations, learning outcomes, formulas, definitions, examples and prerequisites. The same engine handles unrelated subjects without a course-name switch. Enable **material-only** to restrict tutor retrieval and require source-linked quizzes and assignments.

Use **Create viva** to choose material, students, question count, total marks, time, difficulty, question types, Bloom distribution and weighted rubric. Review, edit or regenerate drafts before publishing. Students use **Assigned viva**, hear each question and submit an editable transcript or typed answer. Configured AI proposes evidence-based feedback and marks; **Viva marks review** lets the teacher correct, flag and finalize results. Student history, class analytics and grade notifications use saved results. Follow-ups never add the same question's marks twice.

Follow **docs/UNIVERSAL_VIVA_DEMO.md** for the included two-PDF networking demonstration. Offline generation produces extractive oral questions from the selected passages; semantic evaluation needs a configured provider. Offline responses remain available for teacher grading.

## AI configuration

All secrets belong in `.env` or your secret manager, never source control. `.env.example` contains no real keys.

- `DEMO_MODE=true`: tutor returns labelled source excerpts; no new LLM explanations or questions are fabricated. Course and assessment editors still work.
- `DEMO_MODE=false`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`: compatible `/chat/completions` endpoint. Base URL includes the provider's API prefix, such as `/v1`. Generated tutor citations must reference authorized excerpts. Curriculum and question drafts require teacher approval.
- `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `QDRANT_URL`, optional `QDRANT_API_KEY`, `QDRANT_COLLECTION`: optional semantic retrieval. Use a separate collection for every database/environment. Run `python scripts/reindex_vectors.py` after setup or a failed index operation. New uploads attempt semantic indexing automatically; failures preserve lexical search.
- `SPEECH_BASE_URL`, `SPEECH_API_KEY`, `STT_MODEL`: compatible recorded-audio transcription. `TTS_MODEL`, `TTS_VOICE` enable generated playback. Audio is sent to your selected provider and is not persisted by CampusPath. Provider retention policies still apply.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`: STARTTLS password recovery mail. Without SMTP, recovery clearly reports unavailable; it does not claim to send a message.
- `COOKIE_SECURE=true` for HTTPS deployments. Keep false only for local HTTP development.

Live providers were **not exercised with real credentials** in this environment. Contract, validation, authorization and unavailable-provider tests use controlled responses. Provider configuration does not by itself make the complete application production-ready.

## Materials and multimodal limits

Documents: text PDF, PPTX, DOCX, TXT, Markdown, CSV and supported code files. Source references are actual pages, slides, paragraphs or line ranges. New upload originals and indexed text are retained in the database. Original downloads follow the same ownership rules. A student can explicitly attach a private upload to an assignment, which grants that course’s teachers access to that submitted file. Old 0.1 indexed resources do not gain an original file retroactively.

Images: PNG/JPG/JPEG/WEBP use optional **Tesseract** installed on the host and available on PATH. Set `OCR_LANGUAGE` for installed language packs. OCR is fallible, particularly handwriting; no diagram reasoning is claimed. Scanned PDFs currently require external OCR before upload.

Audio: MP3/WAV/M4A/OGG/WebM need a speech provider. Video: MP4 needs **FFmpeg** plus a speech provider, processes the first five minutes only and does not understand representative frames. Transcript timestamps are not generated when the provider's selected JSON response does not supply them. Media temporary files are deleted. The default upload limit is 8 MiB (configurable up to 64 MiB). PDF extraction defaults to 1,200 pages and 5 million extracted characters. Scoped curriculum/viva operations accept up to 300 chunks, then require a narrower chapter/page selection; curriculum extraction processes batches of 12 rather than silently taking only the first excerpts.

No uploaded code executes. User-supplied web URLs are not fetched. For a public article, upload its permitted text instead.

## Quality evidence

```bash
python -m pytest -q
python scripts/evaluate_retrieval.py
node --check app/static/app.js
node --check app/static/workflows.js
node --check app/static/universal.js
```

At delivery: **94 Python tests passed**, including actual OCR in this environment, and **68 DOM/API integration checks passed**. See `docs/verification.md` for the exact scope and limits. The Starlette/httpx test compatibility deprecation warning is documented; it did not fail tests.

Optional DOM checks require Node only for QA, not to run the application:

```bash
python tests/ui/export_fixtures.py
cd tests/ui
npm install
node dom-check.cjs
# Real in-process API/SQLite workflows without a server:
node integration.cjs
```

Run UI fixture export against a fresh seeded demo database. The integration check creates a temporary database and connects DOM form/click events to FastAPI TestClient; set CAMPUSPATH_TEST_PYTHON to your virtual environment Python when it is not the active python. Fixture checks use API-exported data; they do not measure layout or use a real browser. No screenshots are supplied because actual browser rendering was unavailable. Do not treat these checks as desktop/Android visual verification.

## Docker

```bash
docker compose up --build
# In another terminal, seed only a local demonstration:
docker compose exec campuspath python scripts/seed_demo.py
```

The compose service binds to the local host, persists SQLite in a named volume, runs migrations at startup and runs as an unprivileged user. FFmpeg and Tesseract are optional host/image additions; the base image does not install them. Docker was not available for execution verification here.

## Deployment preparation

`DATABASE_URL` can target PostgreSQL using SQLAlchemy's `postgresql+psycopg://` scheme; install `psycopg[binary]` separately. PostgreSQL compatibility is designed but not integration-tested. Complete the release gates in `docs/deployment.md`: HTTPS, fresh user database, provider credentials, operational controls, backup/restore, concurrency and browser/device acceptance. Do not expose the development server directly to the public internet.

## Structure

- `app/api/`: auth, courses, learning, teaching, generation and speech endpoints.
- `app/auth/`: session, hashing and access policy.
- `app/ai/`: validated providers, structured authoring, lexical and optional hybrid retrieval.
- `app/mastery/`, `app/knowledge_graph/`: deterministic learning/search algorithms.
- `app/documents/`: source extraction, OCR and transcription.
- `app/services/`: learner snapshots and mastery evidence updates.
- `app/static/`, `app/templates/`: responsive browser interface with light/dark themes.
- `migrations/`: frozen v1/v2/v3 schemas and Alembic setup.
- `sample_data/`: sample curriculum, question bank and an actual lecture PPTX.
- `tests/`: privacy, security, learning journey and provider-contract checks.

## Known limitations and roadmap

The full research platform remains unfinished: semantic vision/handwriting, autonomous agent orchestration, causal what-if modeling, code execution/sandbox grading, richer remediation and production operations remain. The saved planner, notifications, configurable mocks, reviewed viva, co-teacher administration and live PCM transport are implemented. Voice transcription still happens per completed turn; live providers and actual browser/microphone behavior need verification. BKT/readiness parameters are uncalibrated; repeated-question and hint discounting reduces but does not eliminate evidence inflation. Public rankings are absent.

See `FINAL_STATUS.md`, `TASKS.md` and `docs/demo_script.md` for what is implemented, what requires a provider and what remains undone.
