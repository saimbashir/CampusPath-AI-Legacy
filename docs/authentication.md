# Authentication

Registration validates identity, password length/matching and unique email/university ID. Teacher selection requires a current faculty invitation. Student profile fields live in `User.profile`; separate StudentProfile/TeacherProfile tables are not implemented.

Login uses Argon2 verification and a dummy hash for nonexistent accounts. It sets an opaque HttpOnly cookie and returns a session-bound CSRF token to the current browser. Every authenticated mutation checks that token. `/api/auth/me` returns only the authenticated account.

Forgot-password creates a short-lived digest-only token and sends it through configured STARTTLS SMTP. Token reset uses an atomic conditional claim and is single use, changes the password and revokes existing sessions. Production concurrency and real email delivery still require environment testing. Email delivery is configuration-dependent and untested against a live SMTP server.

Admin bootstrap and invitation generation are local password-protected commands. Invite plaintext is displayed once for private delivery, not placed in an API response or persisted. Revocation is available in the admin UI. Rotation means revoking and issuing a replacement. CLI execution logs/terminal recordings must be excluded from credential capture by the deployment operator.
