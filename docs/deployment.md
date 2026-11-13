# Deployment gates

This archive prepares a local runnable application and container definition. It is not a verified hosted deployment.

Before inviting real students:
1. Complete missing product capabilities agreed for the course. Present provisional AI viva separately from teacher-confirmed assessment.
2. Use a new database and real passwords; bootstrap a private admin. Do not seed public demo credentials.
3. Put the application behind HTTPS, configure Secure cookies, allowed proxy behavior and request-size limits. Review Host/Origin handling with the actual reverse proxy.
4. Use PostgreSQL for a concurrent deployment, install its driver and integration-test every migration and transaction. Current PostgreSQL support is an architecture target, not a tested deployment.
5. The database rate counter and answer claims are atomic and have targeted concurrency tests. Add provider budgets and verify behavior under sustained production load, including distributed workers and WebSocket admission. The local launch uses one worker.
6. Isolate document/media parsing and add durable background processing. Apply CPU/memory/time limits and maintain parser/FFmpeg/OCR patches.
7. Configure provider keys and SMTP privately; exercise outages, invalid model output, microphone permissions, audio playback and reset-email delivery.
8. Test Android and desktop browsers at 360, 390, 430, 768 and 1024 pixels, keyboard navigation, focus visibility, screen reader labels, reduced motion and light/dark contrast. No rendered browser QA has been completed in this build.
9. SQLite backups and migration downgrade/re-upgrade are tested. Rehearse operator restore, production database backups, account recovery, user deletion/retention and audit access.
10. Run a small faculty pilot and load/concurrency tests before wider use.

Docker Compose binds localhost only. The Dockerfile uses Python 3.12 and a non-root user. Container build/start was not verified because Docker is unavailable in the execution environment. Optional OCR/video binaries and PostgreSQL are not bundled by the default compose configuration.

## Upgrade to 0.3

Run the supplied launcher or python run.py --check --backup to apply 0003_universal_viva with a SQLite backup. Do not replace an existing database with a demo database. Rehearse docs/UNIVERSAL_VIVA_DEMO.md on the actual presentation browser. Configure provider keys privately, verify microphone permission and HTTPS/localhost, and confirm teacher-reviewed marks before treating AI proposals as grades. MAX_UPLOAD_MIB, MAX_PDF_PAGES and MAX_EXTRACTED_CHARS bound extraction; source-generation selections are limited to 300 chunks. Keep the documented single-worker live-socket limitation in mind.
