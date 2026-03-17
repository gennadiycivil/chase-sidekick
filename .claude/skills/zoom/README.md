# Zoom Skill

Command-line interface for Zoom meeting transcripts and AI Companion summaries.

Discovers meetings via Google Calendar, fetches transcripts and summaries from Zoom API.

## Setup

### Step 1: Create a Server-to-Server OAuth App

1. Go to https://marketplace.zoom.us/ and sign in
2. Click **Develop** > **Build App**
3. Choose **Server-to-Server OAuth** app type
4. Enter an app name (e.g., "Sidekick Transcripts")

### Step 2: Add Scopes

In the app configuration, add these scopes:

| Scope | Purpose |
|-------|---------|
| `cloud_recording:read:list_user_recordings:admin` | List recordings for a user |
| `cloud_recording:read:recording:admin` | Download recording files (transcripts) |
| `meeting:read:list_past_instances:admin` | Get past instances of recurring meetings |
| `meeting:read:summary:admin` | Read AI Companion meeting summaries |
| `user:read:user:admin` | Verify user authentication |

### Step 3: Activate the App

1. In the app page, click **Activate your app**
2. Copy the **Account ID**, **Client ID**, and **Client Secret**

### Step 4: Configure

Add credentials to your `.env` file:

```bash
ZOOM_ACCOUNT_ID=your-account-id
ZOOM_CLIENT_ID=your-client-id
ZOOM_CLIENT_SECRET=your-client-secret
ZOOM_USER_EMAIL=you@example.com
```

### Step 5: Verify

```bash
python -m sidekick.clients.zoom auth-test
```

## Commands

All commands use `python -m sidekick.clients.zoom`.

### Auth Test

```bash
python -m sidekick.clients.zoom auth-test
```

Verifies OAuth credentials and shows user info:
```
User: Alice Smith
Email: alice@example.com
ID: abc123
OAuth token exchange: OK
```

### List Recordings

```bash
python -m sidekick.clients.zoom list-recordings
python -m sidekick.clients.zoom list-recordings 2026-02-01 2026-02-28
```

Lists cloud recordings with transcript availability:
```
Found 12 recordings:
  123456789: Team Standup  [2026-03-01 10:00] (30min) [transcript]
  987654321: 1:1 with Bob  [2026-03-01 14:00] (45min)
```

### Find Meetings via Calendar

```bash
python -m sidekick.clients.zoom find-meetings "last week"
python -m sidekick.clients.zoom find-meetings "last 2 weeks" --person alice
python -m sidekick.clients.zoom find-meetings "2026-02-01 to 2026-02-28"
```

Discovers Zoom meetings from Google Calendar events:
```
Searching calendar for Zoom meetings: 2026-02-24 to 2026-03-03
Found 8 Zoom meetings:
  123456789: Team Standup  [2026-03-01 10:00]
  987654321: 1:1 with Bob  [2026-03-01 14:00]
```

Supported date ranges: `today`, `yesterday`, `this week`, `this month`, `last week`, `last N days/weeks/months`, `YYYY-MM-DD to YYYY-MM-DD`

### Download Single Transcript

```bash
python -m sidekick.clients.zoom transcript 123456789
```

Downloads and parses VTT transcript to clean speaker format:
```
Alice Smith: Good morning, let's go over the sprint updates.
Bob Jones: Sure, I finished the API migration yesterday.
Alice Smith: Great, any blockers?
```

### Fetch All Transcripts in Range

```bash
python -m sidekick.clients.zoom transcripts "last week"
python -m sidekick.clients.zoom transcripts "last 2 weeks" --person alice
python -m sidekick.clients.zoom transcripts "last month" --recordings
```

Fetches transcripts for all meetings in a date range:
```
Fetching transcripts: 2026-02-24 to 2026-03-03 (via Google Calendar)
Found 3 transcript(s):

--- Team Standup [2026-03-01 10:00] ---
  Alice Smith: Good morning team
  Bob Jones: Morning!
  ... (15 more lines)
```

Use `--recordings` to discover meetings via Zoom recordings API instead of Google Calendar.

### Get AI Companion Summary

```bash
python -m sidekick.clients.zoom summary 123456789
```

Gets the Zoom AI Companion meeting summary:
```
Meeting: Team Standup
Date: 2026-03-01 10:00
Overview: The team discussed sprint progress and upcoming deadlines...
Topics (3):
  - Sprint progress
  - API migration
  - Upcoming deadlines
Next Steps:
  - Bob to finish API tests by Wednesday
  - Alice to update the roadmap
```

### Fetch All Summaries in Range

```bash
python -m sidekick.clients.zoom summaries "last week"
python -m sidekick.clients.zoom summaries "last 2 weeks" --person alice
```

Fetches AI Companion summaries for all meetings in a date range.

## Dependencies

This client uses Google Calendar for meeting discovery. Ensure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` are configured in `.env` (see the gcalendar skill).

## Python Usage

```python
from sidekick.clients.zoom import ZoomClient, parse_vtt_to_text

client = ZoomClient(
    account_id="your-account-id",
    client_id="your-client-id",
    client_secret="your-client-secret",
    user_email="you@example.com"
)

# List recordings
recordings = client.list_recordings(from_date="2026-02-01", to_date="2026-02-28")

# Download transcript
vtt = client.download_transcript("123456789")
if vtt:
    text = parse_vtt_to_text(vtt)
    print(text)

# Find meetings via Google Calendar
meetings = client.find_meetings_from_calendar("2026-02-01", "2026-02-28", attendee_filter="alice")

# Fetch all transcripts in range
results = client.fetch_transcripts("2026-02-01", "2026-02-28", attendee_filter="alice")
for r in results:
    print(f"{r['topic']}: {r['transcript'][:100]}...")

# Get AI Companion summary
summary = client.get_meeting_summary("meeting-uuid")
if summary:
    print(summary["summary_overview"])
```
