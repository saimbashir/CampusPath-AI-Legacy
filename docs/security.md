# Security design and practical limits

Backend authorization precedes every course, student, resource and analytics query. Teachers are restricted to courses they own or are explicitly assigned to co-teach. Students can query only their own course progress. Personal material is excluded from teacher and peer retrieval. SQL authorization is applied before semantic queries and remote result IDs are checked again afterward. Neither an LLM nor a vector database decides permission.

Passwords use Argon2. Opaque session tokens use 256 bits of randomness; only SHA-256 digests are stored. Cookies are HttpOnly, SameSite=Strict and optionally Secure. Sessions expire after eight hours. Mutation endpoints require a per-session CSRF header. Cross-origin mutation requests are rejected. Logout deletes the server session; reset deletes every session for the account. Registration cannot grant admin privileges, and teacher invitations are consumed with a conditional database update that checks expiry, revocation and use count atomically.

Role and request fields are validated; user-created HTML is escaped in the interface. CSV values are formula-escaped. Course materials are treated as untrusted data. Office archives have an expanded-size limit; file names are reduced to basenames. Code is never run. No arbitrary URL fetch exists. A restrictive CSP excludes third-party scripts. Production upload processing still requires stronger process isolation/resource limits; parsing in a worker thread is not a sandbox.

Login throttling uses atomic shared database upserts and passed a targeted concurrent-budget test. HTTP request bodies are capped even without Content-Length, including chunked requests. Sustained distributed rate limiting and per-account provider cost budgets still need production validation. Mastery updates use an optimistic check on prior probability and attempt count to prevent lost updates from competing runs; a conflict rolls back the answer transaction. Broader production concurrency and database-load tests remain necessary. Replay within the same run is guarded by conditional cursor advancement and a unique answer constraint.

Each course has one owner plus explicitly assigned co-teachers. Administrators can assign/revoke co-teacher access and suspend/reactivate non-admin accounts; suspension revokes existing sessions. Arbitrary role changes are not exposed. Notes are teacher-private; student sharing is not implemented. There is no implemented data deletion/export request workflow for students. Audit records exist but are not a tamper-proof compliance log.

A known demo password is included intentionally for a local synthetic demonstration. A fresh, unseeded database is mandatory for real accounts. Do not reuse the demo database when switching to a real deployment. API documentation is exposed only in demo mode, but disabling demo mode is not a substitute for the release gates.

References used for implementation:
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ (hashing/security primitives; this app uses opaque sessions rather than JWT).
- https://docs.sqlalchemy.org/en/20/dialects/sqlite.html (foreign key enforcement).

## Formal viva controls (0.3)

Only authorized course teachers can author/publish/review; student assignments and session ownership are checked server-side. Draft expected answers are not returned to students. Selected evidence must belong to teacher-provided course resources; private student uploads are excluded. Question source snapshots are persisted for later grading review. Responses use issued-turn checks, while finalization is atomic and rejects repeat grading. A flagged or unreviewed question blocks default teacher finalization. These controls have application tests but do not replace an independent security/load review.
