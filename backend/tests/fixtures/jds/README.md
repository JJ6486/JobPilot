# Job description fixtures

Paste one job description per `.txt` file here, exactly as copied from the portal
(UTF-8, Arabic is fine). Phase 1 tests and `python -m app.cli analyze` run against these.

Required for phase 1 (names matter, the tests look for them):

| File                | What it should be                                                        |
| ------------------- | ------------------------------------------------------------------------ |
| `software_ict.txt`  | A software / ICT role you'd apply to                                     |
| `teaching.txt`      | A computer science or maths teaching role                                |
| `hard_blocker.txt`  | A JD with a condition you can't meet (e.g. "Saudi nationals only")       |
| `arabic.txt`        | A JD written mostly in Arabic                                            |

Any extra files (`extra_1.txt`, ...) are welcome and get used for manual CLI runs.

These files **are committed to git**. Remove recruiter names, phone numbers and
emails if you don't want them in the repo; company names and job text are fine.
If you'd rather keep them out of git entirely, put them in `data/jds/` instead
(gitignored) and tell me.
