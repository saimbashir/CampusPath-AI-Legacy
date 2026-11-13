# CampusPath implementation plan
Deliver one Python application, with server-side authorization preceding every scoped query.
1. Foundation: FastAPI, SQLAlchemy, migrations, opaque sessions and Argon2.
2. Ownership: teacher verification, course/section enrollment, student isolation, audit.
3. Learning loop: material extraction, cited retrieval, editable topic graph, adaptive question bank, Bayesian updates, misconceptions and spaced review.
4. Teaching: scoped student directory, question review, assignments, feedback, notes and analytics.
5. Learning tools: planner, graph, search algorithms and voice/text fallback.
6. Providers: validated generation through an optional compatible API; deterministic demo and explicit unsupported states.
7. Quality: security tests and integration journey; record all gaps in FINAL_STATUS.md.

Release condition: passing automated tests does not equal production readiness. Browser, microphone, provider and deployment verification must be separately reported. Demo measurements are synthetic; computed results must never be forced to match presentation example percentages.
