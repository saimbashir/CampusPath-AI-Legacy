# Voice and viva behavior

The interface uses controlled turns. Start a viva, hear the question, record or type an answer, edit the transcript, then explicitly submit it. Playback stops before recording; navigation and Stop all release microphone resources. Transcripts and feedback are saved; raw live microphone audio is not saved by CampusPath.

When server speech is configured, the Web Audio client sends mono PCM16 frames over an authenticated same-origin WebSocket. A start message supplies the session's CSRF token and sample rate. The server checks course access, allows one active socket per account in the local worker, bounds frames/bytes/time, checks session revocation and performs simple energy-based silence detection. A pause after sufficient speech or Finish answer closes the audio turn. A compatible transcription provider receives a temporary WAV; the returned text remains editable. This is **live audio transport plus per-turn transcription**, not a full-duplex or provider-token-streaming model.

Energy VAD is an approximation: background noise, quiet speakers and accents require device testing. Idle sessions expire. Errors fall back to typed answers. Browsers without Web Audio/WebSocket can use the recorded MediaRecorder endpoint. Without configured STT, browser SpeechRecognition is optional; browser availability and its remote service determine behavior. Generated TTS or browser speech is optional. Microphone access needs localhost or HTTPS.

Viva sessions contain ordered topic questions and saved answers. In provider mode, structured feedback can propose a score and follow-up using course context. Invalid/unavailable provider output falls back to teacher review without inventing an AI score. Offline mode stores the transcript and course-reference guidance. Teachers review the response and enter a confirmed score; only that review adds mastery evidence. A response cannot be reviewed twice through this API. Fluency, accent and identity are excluded from the model prompt. Actual pedagogical quality has not been validated with a live model or students.

The old fixed h(n) keyword endpoint remains for backwards compatibility and is explicitly labelled demo-only. The current UI uses the saved multi-turn workflow instead.

Explicit media file uploads are different from live microphone input: their originals are retained as authorized resources and may be attached to an assignment. External speech providers receive audio/text and the server's provider credential, never the browser session cookie. Provider retention settings still apply.

Backend tests cover origin/auth/course/CSRF rejection, rate/sample validation, malformed/empty audio, concurrent socket rejection, transcript forwarding, revocation, VAD and cleanup. Actual browser microphone/playback, mobile behavior and paid/free provider connectivity were not exercised.

## Formal material-grounded viva (0.3)

Assigned viva uses the same authenticated PCM transport and editable-transcript boundary. It adds source-scoped questions, configurable rubric evaluation, conversation-aware follow-ups, question playback and opt-in listening after playback. Marks are computed from validated criterion percentages and teacher weights. Invalid quotations, unavailable providers or invalid output preserve the answer for teacher review without an invented score. Default official marks require teacher finalization; automatic policy is explicit and confidence-gated. Stop/navigation cancels voice activity; sign-out also clears the oral timer.

Automated acceptance sends generated PCM and controlled STT/LLM responses through the real application APIs. This validates data flow, state, privacy and error handling; it does not establish microphone recognition, speaker playback, latency or real AI grading accuracy.
