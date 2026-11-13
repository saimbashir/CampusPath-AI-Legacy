# Tracked execution status

This tracks release 0.4.1 against the original brief. DONE means the named scope is implemented and verified as stated; it does not mean the entire phase's requested scope is finished.

| Phase | Status | Completed / remaining |
|---|---|---|
| 0 Analysis | DONE | Project, architecture and database plans; original brief retained |
| 1 Foundation | DONE | FastAPI, SQLite, frozen migration, sessions, roles, browser shell; rendered UI verification pending separately |
| 2 Security | DONE | Core isolation, invite, CSRF and session tests; production/load gates remain |
| 3 Courses | DONE | Course-sections, enrollment, scoped material indexing |
| 4 Digital twin | IN PROGRESS | Manual editor and provider draft/review flow; source-linked hierarchical metadata implemented; live generation quality pending |
| 5 RAG | IN PROGRESS | Lexical/citations tested; semantic adapters implemented, live service pending |
| 6 Student model | IN PROGRESS | BKT, diagnostic and prerequisite path; repeat/hint weighting added; calibration and broader assessment evidence pending |
| 7 Assessment | IN PROGRESS | Adaptive MCQs and teacher review; advanced generation/review pending live validation |
| 8 Remediation | IN PROGRESS | Source feedback and revision; measured strategy switching absent |
| 9 Graph | IN PROGRESS | Clickable DOM graph; actual visual/mobile validation pending |
| 10 Voice | IN PROGRESS | PCM WebSocket/energy VAD, editable transcripts, formal scoped viva, rubric marks, follow-ups and teacher finalization implemented; live speech/model and hardware validation pending |
| 11 Multimodal | IN PROGRESS | OCR tested, transcription adapters; vision/handwriting reasoning absent |
| 12 Teacher intelligence | IN PROGRESS | Scoped directory, profiles, notes, analytics, deterministic copilot; full intelligence views pending |
| 13 Study tools | IN PROGRESS | Saved planner, rescheduling, notifications, six-factor readiness and configurable mock exams implemented; background scheduling/calendar integration pending |
| 14 Algorithm lab | DONE | Fixed-graph algorithms and path/cost tests; rendered browser verification pending separately |
| 15 Research | IN PROGRESS | Descriptive research dashboard and labelled retrieval checks implemented; held-out/causal evaluation pending |
| 16 Polish | IN PROGRESS | DOM checks passed; actual browser/microphone/mobile inspection unavailable |
| 17 Testing | IN PROGRESS | 94 backend tests + 68 DOM/API checks; targeted concurrency and upgrades covered; provider/load/browser gates pending |
| 18 Deployment | BLOCKED | Package and Docker definitions prepared; live providers, Docker and hosting not verified |

Further work is listed feature-by-feature in FINAL_STATUS.md. No pending item should be presented as completed in a faculty demonstration.

Release 0.3 acceptance covers AI, Linear Algebra, Computer Networks and Environmental Science through the same runtime course engine. See docs/UNIVERSAL_VIVA_DEMO.md and docs/verification.md.
