# Architecture
Browser HTML/CSS/JS → FastAPI → authentication + course policy → application services → SQLAlchemy → SQLite/PostgreSQL.
All browser mutations use same-origin JSON/multipart and a per-session CSRF header. Passwords use Argon2; session and invite secrets are stored as SHA-256 digests of high-entropy tokens. Course ownership and enrollment filter all data before retrieval or analytics. Students have no directory API.

Learning: course resource → extractor → located chunks → authorized lexical retrieval → optional LLM synthesis → validated citations. Offline retrieval is explicitly lexical, not semantic embeddings. Graph traversal and Bayesian knowledge tracing are deterministic Python. Model results are formative and not official teacher grades.

Use one Uvicorn worker initially. SQLite is a local development database. Production requires HTTPS, PostgreSQL, SMTP, upload isolation, shared rate limiting and operational load testing. No arbitrary URL fetching or uploaded code execution.
