# Start CampusPath AI

**Version 0.4.1 — local demonstration build.** The saved learning and teaching workflows work without an AI key. Optional generated AI and server speech need your own provider settings. Read `FINAL_STATUS.md` for the remaining scope and verification limits.

## Windows

1. Extract the entire ZIP. Open the `campuspath` folder.
2. Install Python **3.12** if it is not installed. Include Python's launcher/PATH option.
3. Double-click **START.bat**. Keep its terminal open. First setup downloads the required packages, creates the database and adds synthetic demo accounts.
4. Open **http://127.0.0.1:8000** in your browser.

If you already have a different supported Python version and the launcher cannot find 3.12, open a terminal in this folder and run `python scripts/bootstrap.py`.

## macOS / Linux

With Python 3.12+ installed, open a terminal in this folder and run:

```bash
sh start.sh
```

Open **http://127.0.0.1:8000**. Initial dependency installation needs internet. Subsequent local demo use does not need a paid AI service.

## Sign in

All local demo accounts use **CampusPath-Demo!2026**.

| Account | Email |
|---|---|
| Student — Saim Bashir / 23F-1234 | saim@campuspath.demo |
| Teacher | teacher@campuspath.demo |
| Administrator | admin@campuspath.demo |

Use separate browser profiles (or a normal and private window) to show student and teacher at the same time. Tabs in the same browser profile share the login session.

## Rehearse these working flows

1. Student: inspect the learning path → complete practice → review results and explanations.
2. Student: save a study plan → mark a task done → reschedule missed work.
3. Teacher: follow **docs/UNIVERSAL_VIVA_DEMO.md** to publish a material-grounded viva. Student: open **Assigned viva** and answer. Teacher: use **Viva marks review** to finalize marks. The separate **Practice viva** remains available.
4. Student: submit an assignment (text or a private upload attachment). Teacher: grade it. Student: view feedback and notification.
5. Student: run a timed mock exam, finish it and inspect the saved topic/CLO results.
6. Teacher: inspect the student directory, private notes, approved question bank and CSV report.

For a reliable first presentation, use **typed viva answers** and the included course material. Test your actual microphone/browser and any provider credentials separately before relying on them.

## If startup fails

- Missing Python: install Python 3.12, reopen the folder and run again.
- Package download failure: check internet access and rerun the launcher. It retries incomplete setup.
- Port already in use: run `python scripts/bootstrap.py --port 8001`, then open http://127.0.0.1:8001.
- Check setup without opening a server: `python scripts/bootstrap.py --check`.
- Back up the SQLite database: `python scripts/bootstrap.py --check --backup`.
- Stop the app: press **Ctrl+C** in its terminal. Start it again with the same launcher; saved work is retained.

Do not delete `campuspath.db` to fix an error: it contains your saved work. Upgrade backups are placed in `backups/`. Keep the entire project folder in a location where your account has write permission.

## Optional AI

The launcher creates `.env` from `.env.example`. Add your own compatible provider URL, model and key there. Set `DEMO_MODE=false` to use configured language-model generation. Restart after changes. Never share your `.env` or paste keys into project code. No credentials are included in this ZIP, and no promise is made that a particular provider will be free.

Use `docs/demo_script.md` for your presentation and `README.md` for manual installation and architecture details.

## Updated theme, practice and voice

The default is now the light blue/ink theme; the theme button retains your saved preference. The demo bank supplies eight questions per topic. For teacher-created courses, upload material, extract/approve concepts, then use Question bank → Generate question batch and approve the drafts. Offline teachers can author questions manually. Small banks display a coverage notice.

For actual AI viva evaluation, configure LLM_BASE_URL, LLM_API_KEY and LLM_MODEL, set DEMO_MODE=false, then restart. Configure the speech settings for server transcription/playback or use supported browser speech. Browser microphone access requires localhost or HTTPS. Teacher review remains the default for official marks. No external-provider credentials are included.
