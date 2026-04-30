---
name: pto
description: Track team PTO from Google Calendar (Workday sync)
---

# PTO Skill

Track team member PTO by reading approved time-off from Google Calendar (synced from Workday).

## Usage

When the user asks about PTO, team availability, or who's out:

```bash
# Check who's out today
python -m sidekick.clients.pto today

# Check who's out tomorrow
python -m sidekick.clients.pto tomorrow

# Check PTO for next 7 days
python -m sidekick.clients.pto week

# Check PTO for next sprint (10 business days = 2 weeks)
python -m sidekick.clients.pto sprint

# Check PTO for next N business days
python -m sidekick.clients.pto sprint 15

# Check PTO for specific date range
python -m sidekick.clients.pto dates 2026-05-01 2026-05-15
```

## Data Source

- **Google Calendar** with Workday PTO sync
- Matches pattern: `{FirstName LastName} - Time-Off`
- Only shows **approved** PTO (not pending requests)

## Limitations

**Important:** This skill only shows PTO that you've **approved** in Workday. If team members have submitted PTO requests that are pending your approval, they won't appear here.

**Before sprint planning:** Check Workday for pending PTO requests to avoid missing unapproved time-off.

## Team Coverage

Tracks PTO for 18 direct reports:
- Nick Larson, Mike Moser, Durgesh Patel, Xiaoxi Jin, Anthony Perello
- Alex Yurowkin, Albert Caldarelli, Bree Devries (new hires as of 2026-04-28)
- Ryan Ward, Calvin Lee, Wyatt Richter, Catherine Lee, Karen Choi
- Swee Yong Chiah, Nathan Aun, Summer Sheldon, Dipo Arowona
- Ben Potter (50% on team)

## Example Output

```
PTO Summary (2026-05-01 to 2026-05-14):
• Nick Larson: Thu May 01
• Wyatt Richter: Thu May 08

Total: 2 person-days
Team availability: 16/18 members
```

## Common Use Cases

**Daily standup:** "Who's out today?"
→ `/pto today`

**Sprint planning:** "Show me PTO for the next sprint"
→ `/pto sprint`

**Team capacity:** "Who will be out next week?"
→ `/pto week`

**Custom range:** "Show me PTO for May 1-15"
→ `/pto dates 2026-05-01 2026-05-15`
