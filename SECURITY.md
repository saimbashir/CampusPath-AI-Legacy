# Security and safe deployment

CampusPath AI is a development build. Keep the GitHub repository **private** until you have inspected the code, demo content and university policies.

- Never commit `.env`, API tokens, service-account files, database files, raw student transcripts or actual grades. `.gitignore` excludes local `.env`, SQLite databases and backup folders.
- `.env.example` contains placeholders only. Configure secrets through the host's secrets manager for real deployment.
- The included demo logins and sample accounts are for local demonstrations only. For real use, initialize a fresh database and create a unique administrator credential using `scripts/manage.py`.
- Uploaded course documents, speech transcripts and AI prompts may contain personal information. Respect institutional consent and retention policies; external LLM/speech services receive the configured requests.
- AI scores are not official grades by default. Teachers review final marks.
- Run tests, an HTTPS deployment review, provider verification and a separate security review before using this for real student assessment.
