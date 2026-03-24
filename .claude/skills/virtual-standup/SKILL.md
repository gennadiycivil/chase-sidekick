---
name: virtual-standup
description: Summarize the daily virtual standup from Slack, grouped by sprint goals
argument-hint: [date]
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
---

# Virtual Standup Summary Skill

Summarize the team's daily virtual standup from Slack, grouped by current sprint goals.

Full rules: `memory/virtual-standup-rules.md`

## Step 1: Determine Current Sprint

Read the sprint calendar from `memory/sprint-calendar.md` and view the image at `memory/2026-sprint-calendar.jpg`. Cross-reference today's date against the sprint date table to determine the current sprint number.

**Report to user:** "Based on the Sprint Calendar, today ({date}) falls within **Sprint {N}** ({start} - {end}). Can you confirm?"

Wait for user confirmation before proceeding. If user corrects the sprint number, use their answer.

## Step 2: Load Sprint Goals

Search Confluence for the sprint planning page:
```bash
python3 -m sidekick.clients.confluence search "SP{N} Sprint Planning" --space CBN --limit 5
```

Then read the page to extract sprint goals (lettered A, B, C, etc.) with DRI and team assignments:
```bash
python3 -m sidekick.clients.confluence read-page PAGE_ID
```

**Report to user:** List the sprint goals found (letter, name, DRI) and confirm these are correct before proceeding.

## Step 3: Find Standup Thread

Get recent messages from the standup Slack channel going back at least 5 days (not a fixed message count — the channel has non-standup chatter that can push threads out of a small window):
```python
from sidekick.clients.slack import SlackClient
from sidekick.config import get_slack_config
from datetime import datetime, timedelta

config = get_slack_config()
client = SlackClient(bot_token=config.get('bot_token',''))

oldest = (datetime.now() - timedelta(days=5)).timestamp()
msgs = client.get_channel_history('C09NU0MEGH1', limit=100)
msgs = [m for m in msgs if float(m.get('ts', 0)) >= oldest]
```

**Date validation (required):** The target date is today's date, or the date provided in $ARGUMENTS. Search through all messages in the 5-day window for a "Stand up report for Browse-and-Navigate-Web-Experience" message from Virtual First Bot whose text contains a date matching the target date.

If no matching thread exists in the team channel, check the Virtual First Bot DM channel for a ping:
```bash
python3 -m sidekick.clients.slack history D0A98HPPTE3 --limit 5
```

Use both signals to determine status:
| Team channel thread? | Bot DM ping? | Conclusion |
|---|---|---|
| Yes | (any) | Standup exists. Proceed to read thread. |
| No | Yes, for target date | Standup was scheduled but no one has responded yet. Report: "Standup thread for {target date} exists but has no responses yet. The bot pinged at {time}. Try again later." |
| No | No, for target date | No standup today. Report: "No virtual standup scheduled for {target date}. Skipping." |

**In the last two cases, stop here. Do not generate a report against a stale thread.**

If a matching thread is found, read the full thread:
```bash
python3 -m sidekick.clients.slack thread C09NU0MEGH1 THREAD_TS
```

To get full untruncated message text, use the Python API directly:
```python
from sidekick.clients.slack import SlackClient
from sidekick.config import get_slack_config
config = get_slack_config()
client = SlackClient(bot_token=config.get('bot_token',''))
replies = client.get_thread_replies('C09NU0MEGH1', 'THREAD_TS')
for msg in replies:
    print(msg.get('text',''))
```

## Step 4: Generate Report

Using the team roster from `CLAUDE.local.md`, the sprint goals from Step 2, and the standup thread from Step 3, generate the summary report.

### Report Format

```
### Standup Summary — {Month} {Day}, {Year}

**Sprint:** {N} ({start_date} - {end_date})
**Sprint Goals Source:** [SP{N} Sprint Planning]({confluence_url})

**Blockers:** {list any blockers, or "None reported."}

**Did Not Respond:** @{handle1} @{handle2}

---

**A. {Sprint Goal A Name}** (DRI: {name})
- **{Person}** — {yesterday summary}. Today: {today plan}.

**B. {Sprint Goal B Name}** (DRI: {name})
- **{Person}** — {yesterday summary}. Today: {today plan}.

{...continue for each sprint goal with activity...}

**Not Aligned to Sprint Goals**
- **{Person}** — {work description}.
```

### Rules

- **Blockers first** — always the first section
- **Sprint reference** — always include sprint number, dates, and link to planning page at the top
- **Did not respond** — use `@{slackhandle}` format (lowercase, no spaces) for Slack @-mentions
- **Exclude from "did not respond"**: Pravi Garg, Hannah Choi (they do not participate in virtual standup)
- **Group by sprint goal** — each person's update under the relevant sprint goal
- **On-call / shadow notation** — italics after name: `**Person** *(primary on-call)*`
- **JIRA ticket references** — include ticket keys (e.g., WEBXP-1234) when mentioned
- **One bullet per person per goal** — combine yesterday + today into a single bullet
- **Omit empty goals** — skip goals with no reported work, unless it's a major goal
- **"Not Aligned to Sprint Goals"** — catch-all for on-call duties, tech debt, cross-team work

## Step 5: Save and Draft

1. Create session directory: `memory/sessions/YYYY-MM-DD-virtual-standup/`
2. Save the report to `memory/sessions/YYYY-MM-DD-virtual-standup/artifacts/standup-report-YYYY-MM-DD.md`
3. Display the report to the user
4. Draft a Slack message version for the user to post — **never post to Slack directly**
