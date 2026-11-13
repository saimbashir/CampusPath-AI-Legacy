# CampusPath AI 0.5.0 — UI refresh and personalized viva practice

**Status: development build.** This version improves an existing project; it does not claim that external AI, speech providers, or production deployment have been verified.

## What changed

1. **Friendlier interface:** calm light/dark themes, clearer cards, responsive spacing, simplified role-specific navigation with secondary features in “More learning tools,” and clearer viva progress displays. Base styles and workflows remain intact; the visual refresh is in `app/static/refresh.css`.
2. **Personalized student practice:** the practice viva accepts **1–30 questions** (default **30**), cycling through **30 different reasoning styles**. Each question uses a teacher-created course topic; its wording and pattern are chosen per saved student session. Reloading or resuming does not change the issued prompt. Submitting the next answer does not silently replace it with the previous answer's follow-up. These question patterns are **locally generated templates**, not LLM output.
3. **Teacher-approved formal viva pool:** teachers may enable personalized selection (default for new vivas), with a random question order per student. If the approved bank contains **more** questions than each student receives, each student can receive a **different subset**. The session persists the chosen approved question IDs, maintaining grading and auditability. For example, approve **40–60 questions** and configure **30 per student**. An expanded bank requires identical marks per question so that every student has the same possible score. If the bank has exactly 30, students get a different order, **not a different question set**.
4. **Extend the draft pool:** teachers can request ten additional grounded drafts via the new “+ 10 more questions” control. If there is insufficient unused source material or the LLM response repeats a question, the operation fails visibly and preserves the existing bank. Teachers must review drafts before publishing when review is enabled. All published questions are locked.
5. **Release accuracy and QA:** application version is 0.5.0. Added regression coverage for unique practice patterns, session stability, isolation and formal question-pool selection, plus a GitHub Actions checks workflow.

## How to use the 30-question feature

**Student practice, offline:** Teacher creates topics or approves extracted curriculum. Student signs in → selects a course → **Practice viva** → selects a topic or “Use my learning path” → **30 questions** → **Start personal viva**. Typed answers work offline. Transcripts are saved for teacher review; offline mode does not invent scores. Question style and wording vary between saved sessions, without introducing unsupported answer facts.

**Formal, source-grounded assessment:** Teacher uploads source material → **Create viva** → chooses number of questions per student (up to 30), marks, duration and audience → enables personalized question selection → generates and approves question drafts → optionally expands the bank → publishes. The backend will not publish an undersized bank or an expanded pool with unequal per-question marks. The full approval, source citation, teacher evaluation and cross-student access controls remain in force.

**Authentic LLM generation/evaluation:** Only with a correctly configured compatible external provider (`DEMO_MODE=false`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`). A reliable internet connection, API quota and selected provider's data-handling practices must be considered. *No account credentials or model are included in the project.* Offline student practice questions remain transparent local prompt templates; teacher authoring uses provider-generated, source-validated drafts where configured.

## Known limits

- This is not a guaranteed anti-cheating system; students can still compare topics or share material. Questions vary but do not guarantee disjoint content between students. Exam integrity requires supervision and appropriate design.
- Generating **30 source-backed formal questions** requires sufficient distinct course passages (or teacher-authored alternatives), and meaningful AI questions need configured provider access.
- Speech recognition depends on the platform/browser or a configured external provider. Use typed responses when unavailable.
- UI syntax, FastAPI integration and SQLite flows were tested in the working environment. Actual mobile/browser rendering, microphone hardware, real provider calls and public deployment must be acceptance-tested separately.
- The packaged demo logins are intentionally synthetic; create a fresh database with a proper administrator and change default settings before any real deployment. Never publish private `.env` files or student data.
