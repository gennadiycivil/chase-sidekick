---
name: zoom_1on1_assets
description: Update or audit configured 1:1 documents for Zoom AI summary links after watched 1:1 meetings. Use when asked to add a Zoom summary to a 1:1 doc, scan recent 1:1s for missing Zoom summaries, backfill end-of-day/week 1:1 Zoom links, or when the user mentions zoom_1on1_assets.
argument-hint: [person|scan interval]
allowed-tools: Bash, Read
---

# Zoom 1:1 Assets

Use Sidekick from `/Users/misterg/projects/misterg-sidekick`.

This skill watches configured 1:1 meetings, finds Zoom AI summary assets, checks the matching 1:1 Google Doc, and adds a dated summary link under the meeting date heading only when approved or explicitly requested.

## Rules

- Read before writing. The command checks the target Google Doc for the Zoom summary doc ID before inserting.
- For "I just met with X, update the 1:1", treat that as permission to apply the update for X.
- For "scan", "end of day", "end of week", or broad intervals, dry-run first, show missing summaries, and ask before applying.
- Final confirmations must include a clickable link to the updated 1:1 doc.
- Default insert is link-only, directly under that meeting's date heading, with this caption: `Summary for MM/DD/YYYY: <Zoom summary link>`.
- Use `--note-style full` only if the user asks for overview/topics/next steps.
- Do not include transcripts unless explicitly requested.

## Common Commands

Just had a meeting with one person:

```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.zoom_1on1_assets scan --person "Alice" --lookback-hours 8
python -m sidekick.clients.zoom_1on1_assets scan --person "Alice" --lookback-hours 8 --apply
```

End-of-day scan:

```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.zoom_1on1_assets scan --lookback-hours 12
```

Weekly scan:

```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.zoom_1on1_assets scan --lookback-hours 168
```

Watch for assets that are still being generated:

```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.zoom_1on1_assets watch --person "Alice" --lookback-hours 8 --poll-seconds 300 --timeout-minutes 120
```

Add approved missing links:

```bash
cd /Users/misterg/projects/misterg-sidekick
python -m sidekick.clients.zoom_1on1_assets scan --lookback-hours 168 --apply
```

## Output Handling

- `already-present`: no write needed.
- `missing-summary`: Zoom summary exists and is missing from the 1:1 doc. Ask before applying unless the user already asked to update that person.
- `pending`: Zoom assets are not generated yet or the exact Zoom instance is not available.
- `inserted`: write completed under the meeting date heading.

When reporting a write, include:

- the person
- the updated 1:1 doc link
- the Zoom summary link
