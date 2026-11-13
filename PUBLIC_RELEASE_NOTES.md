# Public development release notes (v0.5.0)

CampusPath AI is shared as an **in-development portfolio and research demonstration**, not a production-certified student-assessment system.

## What the release includes

- FastAPI application, SQLite/Alembic migrations, HTML/CSS/JavaScript frontend.
- Practice viva session variations and formal viva teacher-approved question selections.
- Classroom workflows, access controls, demo material, reproducible tests and setup guides.
- `.env.example` contains empty provider placeholders; configure real keys privately.

## Important limitations

- Real LLM question generation and automatic semantic evaluation need a configured external provider.
- Teacher approval is required before formal viva questions are published.
- Built-in demo accounts and passwords are strictly for local evaluation. Do not deploy demo accounts publicly.
- Speech and live AI provider interactions require your own end-to-end verification before real use.
- Replace synthetic course content with materials you are permitted to use.

See [README.md](README.md), [START_HERE.md](START_HERE.md), [SECURITY.md](SECURITY.md), [FINAL_STATUS.md](FINAL_STATUS.md), and [docs/RELEASE_0_5_0.md](docs/RELEASE_0_5_0.md).
