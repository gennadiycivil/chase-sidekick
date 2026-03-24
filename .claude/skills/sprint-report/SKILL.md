---
name: sprint-report
description: Fetch and display Core Sprint Reports from core-analytics-server
argument-hint: [summary|tree|dates] [date] [section] [team]
allowed-tools: Bash, Read
---

# Sprint Report Skill

Fetches sprint report data from the Core Sprint Report dashboard.

When invoked, use the sprint report client to handle the request: $ARGUMENTS

## Available Commands

### List Available Sprint Dates
```bash
python -m sidekick.clients.sprint_report dates
```

### Team Summary (default: Browse & Navigate Web experience)
```bash
python -m sidekick.clients.sprint_report summary
python -m sidekick.clients.sprint_report summary 2026-03-16
python -m sidekick.clients.sprint_report summary 2026-03-16 "Core Experience" "Browse & Navigate Web experience"
```

### Workstream Tree (RI -> Epic breakdown with hours, commits, PRs)
```bash
python -m sidekick.clients.sprint_report tree
python -m sidekick.clients.sprint_report tree 2026-03-16
```

### Raw JSON (for programmatic use)
```bash
python -m sidekick.clients.sprint_report raw
```

## Default Behavior

- If no date is specified, uses the latest available sprint
- Default section: "Core Experience"
- Default team: "Browse & Navigate Web experience"

## Data Available

- **Summary**: Issues done %, epics tracked/completed/in-progress, quarterly epic counts
- **Executive Summary**: Auto-generated bullet points
- **Completed Epics**: Epic key, summary, assignee, hours, children count, parent RI
- **Epics In Progress**: With completion percentage
- **Hours by Workstream**: Breakdown of hours per sub-workstream
- **Workstream Tree**: Hierarchical RI -> Epic -> Task view with hours, commits, PRs
- **At Risk Items**: Issues flagged as at risk

## Authentication

Uses browser session cookies stored in `.env` as `SPRINT_REPORT_COOKIES`.
Cookies expire periodically and need to be refreshed from the browser.

To refresh: Open https://core-analytics-server.pp.dropbox.com/sprintreports in Chrome,
open DevTools Network tab, copy cookies from any API request, update `.env`.
