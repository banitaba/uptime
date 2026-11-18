# uptime

Outside uptime check for the sites on the Lightsail server, run by GitHub Actions every 10 minutes.

The server's own watchdog reports problems as BaniSupport tickets. When the whole server is down, neither the
watchdog nor BaniSupport can report it, so this check runs from outside.

- `sites.json` — the public URLs and the expected HTTP status.
- A site is **down** only when all 3 tries, 20 seconds apart, fail.
- A down site gets **one** open issue (labels `down`, `site:<name>`); GitHub emails it to the repo owner. While it stays
  down nothing new is opened. When it answers again, the issue gets a "Recovered at …" comment and is closed.
- Test the alert path: **Actions → uptime → Run workflow** with *test_down* checked (opens an issue for
  `uptime-selftest`), then run it again without it (closes the issue).
- Scheduled runs can start a few minutes late; GitHub sometimes delays schedules by 10–20 minutes.

Python standard library only. Tests: `python3 -m unittest test_check`.
