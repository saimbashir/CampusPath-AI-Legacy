# AI pipeline and review boundaries

Course inputs → parser/OCR/transcription → source-location chunks → authorized lexical/optional hybrid retrieval → validated tutor generation. Offline mode supplies retrieved excerpts and seeded bilingual material. It does not fabricate a new model response.

Curriculum drafting supplies at most 30 course chunks and existing topic names to the provider. Output is schema-validated, checked for duplicate names/cycles and returned for explicit teacher editing. Approval resolves prerequisite names within the authorized course, checks the full DAG and saves in one transaction. Drafting large courses needs better coverage and hierarchical extraction; no completeness claim is made for the first 30 chunks.

Question drafting validates option count, correct index, source ID, topic ownership and exact prompt duplication. Drafts are not saved or approved automatically. The teacher edits and saves the draft, then approves it for student delivery. Bloom consistency, ambiguity and factual correctness still need human review; no independent AI reviewer is claimed.

The product uses separate services and deterministic algorithms. It does not currently implement the full multi-agent orchestration framework requested in the master brief. Provider contracts exist for LLM, embeddings and speech. Version 0.2 implements a separate authenticated PCM WebSocket with energy VAD and completed-turn transcription; it does not claim provider-token streaming.

Unsupported/partial: visual reasoning on diagrams; reliable handwritten mathematical interpretation; representative video frame analysis; speech timestamp alignment; validated general-purpose free-response grading. Viva has a structured provider proposal and teacher-confirmation workflow, whose live pedagogical quality remains unverified. OCR is text recognition, not image understanding.

## Universal evidence pipeline (0.3)

Teacher-selected material is resolved through intersecting file/chapter/page/topic/CLO filters. Curriculum extraction visits batches of 12 over all selected chunks (maximum 300), validates exact quotations and returns a draft for review. Formal question generation validates count, type, difficulty, distribution and citations, followed by a separate provider support verdict. Follow-up evaluation receives prior question/answer context and must also pass source validation. A second model call reduces unsupported output risk but is not a proof of factual accuracy.

The formal engine supports oral/written response formats including numerical reasoning and programming explanations. It does not execute student code. Offline drafts quote real passages; offline semantic scores remain unavailable. Generation can involve several sequential provider calls and inherits configured provider timeouts; no real-time latency guarantee is made. The older MCQ generator validates topic and source IDs but still requires teacher correctness/ambiguity review.
