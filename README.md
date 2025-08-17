# codextest.freykristof.com

## Sprint-feldolgozó (JIRA CSV → snapshotok, napi diff, worklog, burndown, web UI)

Python-alapú eszköz, amely a JIRA CSV exportból naplózott snapshotokat készít, napi változásokat számol, worklogot aggregál, és burndown PNG-t rajzol. Tartozik hozzá egy egyszerű webes felület CSV feltöltéshez és a kimenetek megtekintéséhez.

### Telepítés

1) Python 3.9+
2) Függőségek:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

### CLI használat

```bash
python tools/jira_sprint_processor.py --csv /abszolut/utvonal/export.csv \
  --data-dir ./data/jira_sprint_processor
```

Opcionális:
- `--today YYYY-MM-DD`
- `--sprint-start YYYY-MM-DD --sprint-end YYYY-MM-DD`

Kimenetek (példa):
- `data/jira_sprint_processor/reports/snapshot_2025-08-17.csv`
- `data/jira_sprint_processor/reports/daily_events_2025-08-17.csv`
- `data/jira_sprint_processor/reports/worklogs_2025-08-17.csv`
- `data/jira_sprint_processor/reports/worklogs_daily_2025-08-17.csv`
- `data/jira_sprint_processor/reports/burndown_2025-08-17.{csv,png}`

### Web UI használat

Indítás:

```bash
. .venv/bin/activate
FLASK_APP=web/server.py FLASK_ENV=development flask run --host 0.0.0.0 --port 5000
```

- Böngészőben: `http://localhost:5000`
- Töltsd fel a JIRA CSV-t, a rendszer futtatja a feldolgozást és linkeket ad a generált kimenetekhez.

Megjegyzés: a „kész” státuszok listája: `done, closed, verifiable, verified, accepted, released`.