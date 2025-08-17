# codextest.freykristof.com

## Számológép (TS)

- Fordítás: `npm run build` – a kimenet a `dist/` mappába kerül.
- Megnyitás: nyisd meg az `index.html` fájlt böngészőben.

## Sprint-feldolgozó (JIRA CSV → snapshotok, napi diff, worklog, burndown)

Python-alapú eszköz, amely a JIRA CSV exportból naplózott snapshotokat készít, napi változásokat számol, worklogot aggregál, és burndown PNG-t rajzol.

### Telepítés

1) Python 3.9+
2) Függőségek:

```bash
python3 -m pip install -r requirements.txt
```

### Használat

```bash
python3 tools/jira_sprint_processor.py --csv /abszolut/utvonal/export.csv \
  --data-dir ./data/jira_sprint_processor
```

- A `--data-dir` alapértelmezetten `./data/jira_sprint_processor`.
- Snapshotok: `data/jira_sprint_processor/snapshots_csv/`
- Jelentések: `data/jira_sprint_processor/reports/`

Az eszköz:
- Kinyeri a sprint intervallumot a Sprint mezőből (pl. „B2CP (25) #S16 - 0806 > 0903”).
- Normalizálja a fő mezőket (Key, Summary, Status, Assignee, Story Points, Time Spent, Remaining Estimate, Created, Updated, Sprint).
- Napi snapshotot ment (`snapshot_YYYY-MM-DD.csv`).
- Kiszámolja a napi változásokat az előző snapshothoz képest (új/eltűnt issue, status/assignee/SP/time_spent/remaining_estimate változás).
- Worklog oszlopokból (ha vannak) napi bontást készít a sprint ablakon belül.
- A felgyűlt snapshotokból burndown görbét számol és PNG-t ment.

Opciók:

- `--today YYYY-MM-DD`: dátum felülbírálása (alapértelmezés: mai nap)
- `--sprint-start YYYY-MM-DD --sprint-end YYYY-MM-DD`: sprint ablak kézi megadása

Kimenetek (példa):
- `data/jira_sprint_processor/reports/snapshot_2025-08-17.csv`
- `data/jira_sprint_processor/reports/daily_events_2025-08-17.csv`
- `data/jira_sprint_processor/reports/worklogs_2025-08-17.csv`
- `data/jira_sprint_processor/reports/burndown_2025-08-17.png`

Megjegyzés: a „kész” státuszok listája: `done, closed, verifiable, verified, accepted, released`.