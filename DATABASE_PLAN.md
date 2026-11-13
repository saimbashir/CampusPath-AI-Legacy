# Database plan
User holds role and student/faculty identity and profile attributes. Session, LoginThrottle, TeacherKey and ResetToken manage access.
Course is one course section owned by one teacher. Enrollment connects students to sections. Future many-teacher assignments need a normalized assignment table.
Resource owns located Chunk records. Personal resources carry a private owner; course resources have no private owner. Topic stores CLO and prerequisites as a validated JSON DAG.
Question requires teacher approval. QuizRun persists issued question IDs and cursor. Answer records evidence. Mastery stores posterior, counters and practice date. Revision schedules due dates. Misconception stores evidence.
Assignment/Submission stores teacher-controlled grades. Note is teacher-private. Audit stores sensitive actions without secrets. Conversation stores private text, not raw audio.
Unique constraints prevent duplicate enrollments, mastery records, answer submissions and university identities.
