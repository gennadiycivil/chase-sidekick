# Sprint Report Client

Fetches sprint report data from the Core Sprint Report dashboard at `core-analytics-server.pp.dropbox.com`.

## Setup

### 1. Get Session Cookies

1. Open https://core-analytics-server.pp.dropbox.com/sprintreports in Chrome
2. Open DevTools → Network tab
3. Click any team tab to trigger an API request
4. Right-click a `dates` or `2026-XX-XX` fetch request → Copy → Copy as cURL
5. Extract the cookie values for: `ppa`, `pp_samesite`, `bjar`, `__Secure-untrusted_session`, `t`, `blid`

### 2. Configure .env

Add to your `.env` file:

```bash
SPRINT_REPORT_COOKIES="ppa=...;pp_samesite=...;bjar=...;__Secure-untrusted_session=...;t=...;blid=..."
```

### 3. Test

```bash
python -m sidekick.clients.sprint_report dates
python -m sidekick.clients.sprint_report summary
```

## API Endpoints

- `GET /api/sprintreports/dates` — Available sprint dates
- `GET /api/sprintreports/report/{date}` — Full report for a date

## Cookie Expiry

Session cookies expire periodically. When requests start failing, repeat the browser export process above.

## CLI Usage

```bash
# List sprint dates
python -m sidekick.clients.sprint_report dates

# Team summary (defaults to Browse & Navigate Web experience)
python -m sidekick.clients.sprint_report summary

# Specific date and team
python -m sidekick.clients.sprint_report summary 2026-03-16 "Core Experience" "Desktop Experience"

# Workstream tree
python -m sidekick.clients.sprint_report tree

# Raw JSON
python -m sidekick.clients.sprint_report raw
```

## Python Usage

```python
from sidekick.clients.sprint_report import SprintReportClient

client = SprintReportClient(cookies="ppa=...;pp_samesite=...")

# Get available dates
dates = client.get_dates()

# Get team report
banner = client.get_team_report(
    date="2026-03-16",
    section="Core Experience",
    team="Browse & Navigate Web experience"
)

print(banner["summary_cards"])
print(banner["executive_summary"])
print(banner["completed_epics"])
```
