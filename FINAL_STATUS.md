> **Update — 0.5.0 (November 2026):** This document records the earlier 0.4.1 baseline. Version 0.5.0 adds a visual refresh, 30 distinct offline student-practice patterns, and optional per-student selection from a larger teacher-approved formal-viva pool. See [Release 0.5.0](docs/RELEASE_0_5_0.md) for the updated functionality and limits. External provider and mobile hardware verification remain outstanding.

# CampusPath AI — release status

**Version 0.4.1 · 10 October 2026 · tested development build**

The project now supports a connected, persistent student/teacher demonstration. It is runnable Python source, not only a dashboard mockup. The original master brief is still **not fully complete**, and this release has not been certified for a real university deployment.

“Tested” below means the specific backend, migration or DOM/API integration behavior was exercised. Actual browser rendering, Android, microphone hardware and live external providers were unavailable for verification. No zero-crash guarantee is made.

| Area | Implemented and tested scope | Remaining boundary |
|---|---|---|
| Local startup | Setup/check command, idempotent seed, migration, SQLite integrity checks and backups before an upgrade | Python and first-install internet required; Windows batch launcher not executed on Windows |
| Authentication | Argon2 passwords, digest-only sessions, CSRF, logout/expiry, profile edit and password/session revocation | Email verification absent; recovery delivery needs SMTP |
| Faculty invitations | Hash, expiry, revoke, use limit, atomic claim and audited CLI issuance | No browser secret-issuance form |
| Privacy | Own-student records, enrolled courses, teacher section ownership and co-teacher assignment | Deployment/retention controls and independent security review pending |
| Administration | Users, suspension/reactivation, session revocation, co-teacher assignment/removal, configuration status and audit log | No billing, provider-budget management or arbitrary role changes |
| Rate limits | Atomic shared database counters; concurrent acceptance-budget test | Sustained/distributed production load not certified |
| Course management | Sections, enrollment, topic/CLO/prerequisite editing, DAG validation and approved bank | Book/chapter/section/subtopic metadata is stored as validated JSON; normalized Section/CLO entities remain absent |
| Resources | Authorized located excerpts; retained originals and downloads for new uploads | Old 0.1 uploads retain excerpts only; original files cannot be reconstructed |
| Documents | Text PDF, PPTX, DOCX, text/code extraction; actual OCR test | Scanned PDF OCR, diagram understanding and reliable handwriting interpretation absent |
| Audio/video uploads | Compatible transcription; FFmpeg extracts first five video minutes | Live credentials required; no video-frame interpretation or timestamp alignment |
| Retrieval | Lexical search, actual source locations, scoped optional hybrid/Qdrant adapter | Live semantic service not exercised; lexical benchmark is a small smoke test |
| Tutor | Source-grounded excerpts offline, validated compatible LLM/citation adapter, explanation modes | Offline mode does not generate new prose; live factual faithfulness unverified |
| Authoring | Manual and provider-generated curriculum/question drafts, validation and teacher approval | Live generation and independent AI quality review pending |
| Adaptive assessment | Approved MCQs, difficulty progression, diagnostic interleaving, saved history, resume and answer-replay guard | Standalone adaptive assessment remains MCQ-based; formal viva supports typed/oral responses and provider evaluation, without executing code |
| Mock exams | Topic filter/API multi-topic selection, marks, time, difficulty, exact joint CLO/Bloom quotas, results and early finish | No proctoring; rejected infeasible distributions need more approved questions |
| Knowledge tracing | BKT-inspired state, prior/posterior evidence, option-count guess rate, repeat/hint discount, observed elapsed time | Uncalibrated; time is reported, not used to infer ability; attempt confidence remains a proxy |
| Learning path | Weak prerequisites before dependent topics, explanations, misconceptions and spaced revision | No causal root-cause diagnosis or measured strategy-switching agent |
| Readiness | Six explicit factors: mastery, coverage, accuracy, recent mocks, assessed strong concepts, practice recency | Descriptive uncalibrated indicator; missing evidence contributes zero, not an invented grade |
| Study plan | Persisted daily budget/weekday plan, completion/skip, archive, missed-work rescheduling and overflow disclosure | UTC dates; no automatic background scheduler or calendar-provider sync |
| Inbox | Persisted deduplicated revision/assignment/review/grade notifications and read state | Refreshed on access, not push/email delivery |
| Formal viva | Teacher-selected sources/students, time/marks/rubric/type/Bloom configuration, quoted drafts, approval/publish, editable transcripts, structured rubric marks, grounded follow-ups, teacher finalization and analytics | Offline mode leaves semantic AI score unavailable; real provider quality and hardware require acceptance |
| Viva mastery | Finalized teacher reviews update evidence once per main question; provisional and confirmed marks remain separate | Update weight is illustrative, not calibrated; explicit auto-finalization never updates mastery |
| Live voice transport | Authenticated same-origin PCM WebSocket, CSRF handshake, bounded frames, energy-based silence detection, revocation, cleanup | One worker/in-memory active socket guard; transcribes completed turns, not provider token streaming; hardware unverified |
| Voice fallbacks | Browser recognition/playback, MediaRecorder compatibility fallback, typed input, stop controls | Browser services may require internet; no automatic full-duplex conversation |
| Raw microphone privacy | Application does not persist live microphone audio | Configured providers may retain it; explicitly uploaded media originals are stored as resources |
| Assignments | Text/private-file submission, authorized original download, teacher grading, overwrite protection and notifications | AI formative assignment feedback absent |
| Teacher intelligence | Directory, search/filter/sort, mastery/readiness/viva, Bloom, revisions/streak, private notes and CSV | Full longitudinal intervention modeling absent |
| Copilot | Actual scoped learner data with an explicit deterministic remedial-activity template | Not autonomous or general LLM teacher reasoning |
| Research | Saved evidence counts/changes, AI draft current approval rate, AI/teacher viva error and labelled retrieval evaluation | No held-out/causal learning-effect study, model-comparison experiments or intervention prediction |
| Algorithm lab | BFS/DFS/UCS/A* fixed-graph steps and costs | No graph editor; actual visual inspection pending |
| Interface | Student/teacher/admin screens, forms, error/empty/loading states, escaping and real API-connected workflows | CSS responsive themes implemented; desktop/mobile visual/accessibility acceptance still required |
| Database | Frozen v1/v2/v3 migrations, fresh setup, populated v1 upgrade, backup and rollback/re-upgrade checks | PostgreSQL not integration-tested; backups are SQLite-specific |
| Deployment | Local launcher, locked dependencies, Docker definitions and operator guidance | Docker build, hosting, HTTPS proxy and sustained load unverified |

## This session’s upgrade

Release 0.3 adds the subject-independent material curriculum, book/chapter/page scopes, material-only policy, source-linked assessments and configurable formal viva. Source citations are validated against exact supplied quotations. Generated questions and follow-ups receive a second provider support check. Teacher review is the default; optional automatic finalization requires explicit configuration and sufficiently confident scores. Final grades, per-question feedback, notifications and teacher analytics are persisted and access-controlled.

The previous planner, adaptive MCQs, mock exams, assignments, administration and practice viva remain available. See docs/verification.md for the executed checks and docs/UNIVERSAL_VIVA_DEMO.md for a rehearsal.

Remaining large master-brief items include semantic vision/handwriting, autonomous multi-agent orchestration, causal intervention modeling, executable coding assessment, production operations and a real faculty/browser pilot. The application does not claim perfect AI judgment or zero crashes.

## Release 0.4 improvements

Paper/ink/blue theme; eight-question demo topic checks; teacher-generated batches of 4–20 source-grounded MCQs; fresh-upload and abbreviation-aware tutor retrieval; structured teaching feedback; bounded mastery updates and breadth/reassessment gates; TTS-to-browser fallback with safe microphone timing. Existing saved records remain intact. All production/device/provider verification boundaries above still apply.
