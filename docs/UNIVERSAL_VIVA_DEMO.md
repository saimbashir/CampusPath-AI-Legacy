# Universal course and viva demonstration — 0.3.0

This is a repeatable demonstration using original, included teaching notes. The networking subject is sample data, not a condition in the course engine.

## Prepare the course

1. Start the app with START.bat (Windows) or sh start.sh (macOS/Linux). Sign in as teacher@campuspath.demo with CampusPath-Demo!2026.
2. Create a Computer Networks course/section. Copy its generated enrollment code. In another browser profile, sign in as saim@campuspath.demo and join that course. Separate tabs share a session, so use separate profiles or a private window.
3. As the teacher, upload sample_data/universal/CN_Lecture_01.pdf and CN_Lecture_02.pdf using the material upload screen. They contain switching/routing and TCP notes. Original text versions are alongside the PDFs.
4. Open Material curriculum. Select both files, extract the structure, inspect the proposed concepts and exact citations, then approve. Correct chapter/page metadata if needed. All selected filters intersect, so clear incompatible filters before broadening the selection.
5. Enable material-only if required. Existing questions or assignments without supporting chunk IDs are excluded from student use under this policy. The source catalog shows the chunk IDs needed in the editors.

## Create and publish a viva

1. Open Create viva in the active course. Select both PDFs and Saim Bashir (or leave the students selection empty for every enrolled student).
2. Set title to Computer Networks — Lectures 01–02, 5 questions, 25 marks, 20 minutes, Mixed difficulty, and Oral Viva question type. Keep question review and teacher marks review enabled. Start with follow-up depth 1 and immediate feedback enabled. Optional availability timestamps are handled in UTC by the server.
3. Generate drafts. In demo mode these are extractive prompts supported by actual passages. With configured language-model settings, generation proposes varied questions and expected answers, validates exact quotations and separately checks material support. Unsupported or invalid generation is rejected.
4. Inspect expected concepts, acceptable points, source quotations and marks. Edit or regenerate any draft that is unclear. Editing/regeneration requires approval again. Approve all five and publish. The server requires the configured question count and exact total marks.
5. Published questions are immutable. Create another viva if an already published paper must change. Each student has one saved session per viva, which can be resumed.

## Student oral flow

1. Open Assigned viva, select the published exam and start. The countdown and marks appear with the current question.
2. Use Hear question, then Record. Finish/Stop ends capture; review and edit the transcript before submitting. Automatic listening after question playback is opt-in. Allow browser microphone permission; use localhost or HTTPS.
3. Typed answers use the same evaluation path and work without microphone hardware. A completed voice turn is transcribed; this is not word-by-word provider streaming.
4. Configured AI reports correct, incorrect and missing points, misconceptions, rubric contributions and proposed marks. Follow-ups use the previous conversation and selected material. The last evaluation for a main question replaces its earlier proposal rather than increasing the total available marks.
5. Without an available provider, the answer is still saved for teacher review and no semantic AI score is invented. Delayed-feedback exams hide evaluation until completion. A timer expiry or early finish retains the recorded work and treats unanswered items as unanswered.

## Teacher marks and results

1. Open Viva marks review and search by student name or university ID.
2. Read each question's transcripts, expected points, citations and AI rubric breakdown. Enter a confirmed mark and feedback for every main question. Flag uncertain responses for attention; flagged items prevent finalization.
3. Finalize after all reviews are complete. This commits official marks once, creates the student's grade notification and updates mapped concept evidence once per question. Repeated finalization is rejected.
4. The student can see their own confirmed results. The teacher can see the course's Viva analytics and directory averages. Another student cannot view this session.
5. Scores such as 20/25 or 21/25 are examples, not forced output. Actual marks follow submitted answers, provider evaluation and teacher decisions.

## Configure semantic AI and speech

Put a compatible language-model base URL, model and API key in .env, set DEMO_MODE=false, and restart. Set SPEECH_BASE_URL, SPEECH_API_KEY and STT_MODEL for server transcription; set TTS_MODEL/TTS_VOICE for provider playback. Browser recognition/playback are fallbacks where supported. No real keys are included, and the app cannot obtain an account's private key automatically. A compatible local endpoint can be configured, but model availability and hardware requirements depend on that installation.

Run a full microphone → transcript → feedback → playback rehearsal on the presentation device. The automated suite uses controlled provider outputs and generated PCM to verify transport/contracts, not actual speech recognition or grading quality.

## Other subjects and scale

Create Linear Algebra, Artificial Intelligence or Environmental Science as ordinary courses; upload the teacher's actual material and repeat these steps. Test fixtures exercise all four subjects through shared APIs. Numerical/programming responses are evaluated as text against a configured rubric; uploaded code is never executed.

Default limits: 8 MiB per upload, 1,200 PDF pages and 5 million extracted characters. Environment settings can raise the byte limit to 64 MiB. Curriculum/viva selection is bounded to 300 chunks; choose chapters/pages for larger books. Curriculum extraction visits every selected chunk in batches of 12. Scanned PDFs need external OCR before upload. Large live jobs can take multiple sequential provider calls, especially when validating individual questions.
