# Search Commands for Google Calendar and Google Docs

This guide covers the native search functionality added to the Google Calendar and Google Docs clients.

## Table of Contents
- [Google Calendar Search](#google-calendar-search)
- [Google Docs Search](#google-docs-search)
- [Common Use Cases](#common-use-cases)
- [Integration with Other Tools](#integration-with-other-tools)

---

## Google Calendar Search

### Command: `search-events`

Search for calendar events by text query. Searches across event **title, description, location, and attendee names/emails**.

### Syntax

```bash
python -m sidekick.clients.gcalendar search-events <query> [time_min] [time_max] [max_results]
```

### Parameters

- **query** (required): Free text search query
- **time_min** (optional): Start time in RFC3339 format (e.g., `2024-01-01T00:00:00Z`)
- **time_max** (optional): End time in RFC3339 format
- **max_results** (optional): Maximum number of events to return (default: 100)

### Examples

#### Find all meetings with a specific person

```bash
# Search for all events with "Ned Lindau" (searches attendee names/emails)
python -m sidekick.clients.gcalendar search-events "Ned Lindau" "2026-04-01T00:00:00Z" "2026-05-12T23:59:59Z" 100
```

**Output:**
```
Found 18 events matching 'Ned Lindau':

01pjg60fbaiq1kkf9ao75biqnr_20260428T170000Z: Up Next Party 🎉
  2026-04-28 13:00
  Attendees: nicklarson@dropbox.com, misterg@dropbox.com, nlindau@dropbox.com, ...

d048lpuvlbssstobfks6bothoh_20260429T153000Z: Bridge v2 Daily Standup
  2026-04-29 11:30
  Attendees: pgarg@dropbox.com, misterg@dropbox.com, nlindau@dropbox.com, ...
```

#### Find all events about a topic

```bash
# Search for events with "Bridge V2" in title or description
python -m sidekick.clients.gcalendar search-events "Bridge V2" "2026-04-01T00:00:00Z" "2026-05-12T23:59:59Z"
```

#### Search by email address

```bash
# Search using email address
python -m sidekick.clients.gcalendar search-events "nlindau@dropbox.com" "2026-04-01T00:00:00Z" "2026-05-12T23:59:59Z" 200
```

#### Search without date range

```bash
# Search all time (omit time_min and time_max)
python -m sidekick.clients.gcalendar search-events "quarterly planning"
```

### What Gets Searched

The Google Calendar API `q` parameter searches:
- ✅ Event title/summary
- ✅ Event description
- ✅ Event location
- ✅ Attendee names
- ✅ Attendee email addresses

### Output Format

Each event shows:
- Event ID
- Event title/summary
- Start time (with "all-day" notation if applicable)
- Location (if present)
- **Attendee list** (email addresses)

---

## Google Docs Search

### Command: `search`

Search for Google Docs by text query. Searches document **name and full text content**.

### Syntax

```bash
python -m sidekick.clients.gdocs search <query> [max_results]
```

### Parameters

- **query** (required): Free text search query
- **max_results** (optional): Maximum number of documents to return (default: 25, max: 100)

### Examples

#### Find documents mentioning a person

```bash
# Search for all docs containing "Ned Lindau"
python -m sidekick.clients.gdocs search "Ned Lindau" 50
```

**Output:**
```
Found 1 documents matching 'Ned Lindau':

1kwf6zlt3m5Dt1-HIpdtv2Or_9MxrZvtxvD-f661c5QM: Pravi Gennadiy 1:1
  Modified: 2026-05-12
  Owners: misterg@dropbox.com
  URL: https://docs.google.com/document/d/1kwf6zlt3m5Dt1-HIpdtv2Or_9MxrZvtxvD-f661c5QM/edit
```

#### Find documents about a project

```bash
# Search for docs about "Bridge V2"
python -m sidekick.clients.gdocs search "Bridge V2" 10
```

#### Search for specific phrases

```bash
# Search for exact phrase (use quotes)
python -m sidekick.clients.gdocs search "recommendation engine"
```

#### Get more results

```bash
# Increase max results (up to 100)
python -m sidekick.clients.gdocs search "quarterly planning" 100
```

### What Gets Searched

The Google Drive API `fullText` search searches:
- ✅ Document title/name
- ✅ Full document text content (all paragraphs, tables, etc.)
- ✅ All tabs in documents with multiple tabs

### Filtering

- **Only searches Google Docs** (not Sheets, Slides, PDFs, etc.)
- Returns documents you have **view or edit access** to
- Results ordered by **most recently modified** first

### Output Format

Each document shows:
- Document ID
- Document name/title
- Last modified date (YYYY-MM-DD)
- Owner email addresses
- Direct URL to view/edit the document

### Reading Search Results

After finding documents, read their content:

```bash
# Read full document by ID
python -m sidekick.clients.gdocs read 1kwf6zlt3m5Dt1-HIpdtv2Or_9MxrZvtxvD-f661c5QM

# Read by URL
python -m sidekick.clients.gdocs read-url "https://docs.google.com/document/d/1kwf6zlt3m5Dt1-HIpdtv2Or_9MxrZvtxvD-f661c5QM/edit"
```

---

## Common Use Cases

### Find All Interactions with a Person

Combine calendar and docs searches:

```bash
# 1. Find all meetings with the person
python -m sidekick.clients.gcalendar search-events "Ned Lindau" "2026-01-01T00:00:00Z" "2026-12-31T23:59:59Z" 100

# 2. Find all docs mentioning the person
python -m sidekick.clients.gdocs search "Ned Lindau" 50

# 3. Also search Slack, Gmail, etc.
python -m sidekick.clients.slack search "Ned Lindau"
python -m sidekick.clients.gmail search "Ned Lindau"
```

### Track Project Activity

```bash
# Calendar: Find all project meetings
python -m sidekick.clients.gcalendar search-events "Project Apollo" "2026-01-01T00:00:00Z" "2026-12-31T23:59:59Z"

# Docs: Find all project documentation
python -m sidekick.clients.gdocs search "Project Apollo" 100
```

### Prepare for a Meeting

```bash
# Find previous meetings with attendees
python -m sidekick.clients.gcalendar search-events "alice@example.com" "2026-01-01T00:00:00Z" "2026-05-12T23:59:59Z"

# Find shared documents
python -m sidekick.clients.gdocs search "alice" 25
```

### Audit Participation

```bash
# Find all meetings you attended with a specific team
python -m sidekick.clients.gcalendar search-events "Platform Team" "2026-01-01T00:00:00Z" "2026-03-31T23:59:59Z" 200

# Count events
python -m sidekick.clients.gcalendar search-events "Platform Team" "2026-01-01T00:00:00Z" "2026-03-31T23:59:59Z" 200 | grep "Found"
```

### Research Past Decisions

```bash
# Search meeting notes in docs
python -m sidekick.clients.gdocs search "decision to migrate" 50

# Search calendar for decision meetings
python -m sidekick.clients.gcalendar search-events "architecture decision" "2025-01-01T00:00:00Z" "2026-12-31T23:59:59Z"
```

---

## Integration with Other Tools

### Piping and Filtering

Extract specific information:

```bash
# Get just event IDs
python -m sidekick.clients.gcalendar search-events "standup" | grep -oE '^[a-z0-9_]+:'

# Get just document URLs
python -m sidekick.clients.gdocs search "1:1" | grep "URL:"

# Count results
python -m sidekick.clients.gcalendar search-events "All Hands" | grep "Found" | grep -oE '[0-9]+ events'
```

### Scripting Examples

Bash script to find all interactions:

```bash
#!/bin/bash
PERSON="$1"
START="2026-01-01T00:00:00Z"
END="2026-12-31T23:59:59Z"

echo "=== Calendar Events ==="
python -m sidekick.clients.gcalendar search-events "$PERSON" "$START" "$END" 100

echo ""
echo "=== Google Docs ==="
python -m sidekick.clients.gdocs search "$PERSON" 50

echo ""
echo "=== Slack Messages ==="
python -m sidekick.clients.slack search "$PERSON"
```

Usage:
```bash
chmod +x find_interactions.sh
./find_interactions.sh "Ned Lindau"
```

### Python Integration

Use the clients programmatically:

```python
from sidekick.clients.gcalendar import GCalendarClient
from sidekick.clients.gdocs import GDocsClient
from sidekick.config import get_google_config

config = get_google_config()

# Calendar search
calendar = GCalendarClient(
    client_id=config["client_id"],
    client_secret=config["client_secret"],
    refresh_token=config["refresh_token"]
)

events = calendar.search_events(
    query="Ned Lindau",
    time_min="2026-04-01T00:00:00Z",
    time_max="2026-05-12T23:59:59Z",
    max_results=100
)

print(f"Found {len(events)} events")
for event in events:
    print(f"- {event['summary']} at {event['start'].get('dateTime', event['start'].get('date'))}")

# Docs search
docs = GDocsClient(
    client_id=config["client_id"],
    client_secret=config["client_secret"],
    refresh_token=config["refresh_token"]
)

documents = docs.search_documents("Ned Lindau", max_results=50)

print(f"\nFound {len(documents)} documents")
for doc in documents:
    print(f"- {doc['name']} (modified {doc['modifiedTime'][:10]})")
    
    # Read document content
    content = docs.read_document(doc['id'])
    print(f"  Preview: {content[:100]}...")
```

---

## Comparison with Previous Methods

### Before (Multi-Step Workaround)

**Calendar:**
```bash
# Old way: list all events, then grep
python -m sidekick.clients.gcalendar list "2026-04-01T00:00:00Z" "2026-05-12T23:59:59Z" 500 | grep "Ned"
# Problem: Only searched titles, not attendees
```

**Docs:**
```bash
# Old way: search Gmail for doc links, extract IDs, then read
python -m sidekick.clients.gmail search "docs.google.com Ned Lindau"
# Manually extract doc ID from results
python -m sidekick.clients.gdocs read <doc_id>
# Problem: Multi-step, manual extraction, misses docs not shared via Gmail
```

### After (Native Search)

**Calendar:**
```bash
# New way: direct search including attendees
python -m sidekick.clients.gcalendar search-events "Ned Lindau" "2026-04-01T00:00:00Z" "2026-05-12T23:59:59Z" 100
# ✅ Searches attendees, title, description, location
# ✅ Shows attendee list in output
```

**Docs:**
```bash
# New way: direct full-text search
python -m sidekick.clients.gdocs search "Ned Lindau" 50
# ✅ Searches document name AND content
# ✅ Finds all accessible docs, not just shared via Gmail
# ✅ Returns doc IDs ready to read
```

---

## Troubleshooting

### No Results Found

1. **Check date range** (Calendar): Make sure time_min and time_max cover the expected period
2. **Check permissions** (Docs): You can only find docs you have access to
3. **Try broader search**: Use shorter/simpler query terms
4. **Check spelling**: Search is case-insensitive but spelling matters

### Too Many Results

1. **Narrow date range** (Calendar): Use more specific time_min/time_max
2. **Reduce max_results**: Lower the max_results parameter
3. **Use more specific query**: Add more keywords or use exact phrases

### API Errors

- **401 Unauthorized**: OAuth token expired, run the client again (it auto-refreshes)
- **403 Forbidden**: Check API permissions in Google Cloud Console
- **Rate limits**: Google Calendar API allows 1M requests/day (unlikely to hit)

### Performance

- Calendar searches are fast (< 1 second typically)
- Docs searches can be slower for large result sets (2-5 seconds)
- Use smaller max_results values for faster responses

---

## Related Documentation

- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- [Google Drive API Documentation](https://developers.google.com/drive/api)
- [Main README](../README.md)
- [CLAUDE.md](../CLAUDE.md) - Project architecture and patterns

## OAuth Setup

Both search commands require Google OAuth2 credentials. See main README for setup instructions:

1. Create Google Cloud project
2. Enable Calendar API and Drive API
3. Create OAuth2 credentials
4. Add credentials to `.env` file
5. Run authentication flow to get refresh token

---

## Technical Details

### Google Calendar Search Implementation

- Uses Google Calendar API v3 `events.list` endpoint
- Query parameter: `q` (free text search)
- Searches: title, description, location, attendee names/emails
- Returns: All event fields including attendees array

### Google Docs Search Implementation

- Uses Google Drive API v3 `files.list` endpoint
- Query: `mimeType='application/vnd.google-apps.document' and fullText contains 'query'`
- Searches: Document name and full text content
- Returns: Document metadata (id, name, modifiedTime, owners, webViewLink)
- Ordered by: `modifiedTime desc` (most recently modified first)

### API Call Tracking

Both clients track API call count in `client.api_call_count` for debugging and monitoring.

---

## FAQ

**Q: Does calendar search show events I declined?**  
A: Yes, it searches all events on your calendar regardless of RSVP status.

**Q: Can I search for documents owned by someone else?**  
A: Yes, if they're shared with you. Ownership doesn't affect search, only access permissions.

**Q: Does docs search work with Google Sheets or Slides?**  
A: No, it only searches Google Docs. Use Drive API directly for other file types.

**Q: Can I search for events I'm not invited to?**  
A: No, you can only search your own calendar and events you're invited to.

**Q: Are search results cached?**  
A: No, every search hits the Google API for fresh results.

**Q: Can I search within a specific doc instead of searching all docs?**  
A: Yes, use `python -m sidekick.clients.gdocs read <doc_id>` then grep/search the output.

---

**Last Updated:** 2026-05-12  
**Version:** 1.0.0  
**Contributors:** Claude Sonnet 4.5, Gennadiy Civil
