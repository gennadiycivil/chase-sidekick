# Google Drive Skill

Command-line interface for searching and browsing Google Drive files.

## Setup

Uses the same Google OAuth2 credentials as Gmail, Calendar, and Sheets. If you already have `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` in your `.env`, you're ready to go.

### Additional Scope Required

| Scope | Purpose |
|-------|---------|
| `https://www.googleapis.com/auth/drive.readonly` | Search and read file metadata from Google Drive |

### Configure

```bash
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token
```

## Commands

All commands use `python -m sidekick.clients.gdrive`.

### Search by Name

```bash
python -m sidekick.clients.gdrive find "sprint report"
python -m sidekick.clients.gdrive find "sprint report" doc
python -m sidekick.clients.gdrive find "budget" sheet
```

Searches files by name. Optional type filter: `doc`, `sheet`, `slide`, `folder`, `pdf`, `form`.

```
Found 3 files:
  Sprint Report Q1  [g:document]  2026-03-01  https://docs.google.com/...
  Sprint Report Q2  [g:document]  2026-02-15  https://docs.google.com/...
  Sprint Reports    [g:folder]    2026-01-10  https://drive.google.com/...
```

### Full-Text Search

```bash
python -m sidekick.clients.gdrive fulltext "migration plan"
python -m sidekick.clients.gdrive fulltext "migration plan" doc
```

Searches inside file contents:
```
Found 2 files:
  API Migration Plan  [g:document]  2026-03-01  https://docs.google.com/...
  Tech Spec v2        [g:document]  2026-02-20  https://docs.google.com/...
```

### My Files

```bash
python -m sidekick.clients.gdrive mine
python -m sidekick.clients.gdrive mine "report" doc
```

Lists files owned by you, optionally filtered by name and type.

### Recently Viewed

```bash
python -m sidekick.clients.gdrive recent
python -m sidekick.clients.gdrive recent sheet
```

Lists recently viewed files, sorted by last viewed time.

### List Folder Contents

```bash
python -m sidekick.clients.gdrive ls FOLDER_ID
python -m sidekick.clients.gdrive ls root
```

Lists files in a specific folder (use `root` for the root folder).

### Raw Query

```bash
python -m sidekick.clients.gdrive search "name contains 'report' and mimeType = 'application/vnd.google-apps.document'"
```

Executes a raw Drive API query string.

### Get File Metadata

```bash
python -m sidekick.clients.gdrive get FILE_ID
```

Shows detailed metadata:
```
Name: Sprint Report Q1
Type: application/vnd.google-apps.document
Modified: 2026-03-01T10:30:00.000Z
Created: 2026-01-15T08:00:00.000Z
Owner: Alice Smith
URL: https://docs.google.com/document/d/1abc123/edit
```

## Python Usage

```python
from sidekick.clients.gdrive import GDriveClient, MIME_TYPES

client = GDriveClient(
    client_id="your-client-id",
    client_secret="your-client-secret",
    refresh_token="your-refresh-token"
)

# Search by name
result = client.search_by_name("sprint report", mime_type="doc")
for f in result["files"]:
    print(f"{f['name']} - {f['webViewLink']}")

# Full-text content search
result = client.search_fulltext("migration plan")

# Files owned by me
result = client.search_owned_by_me(name="report", mime_type="sheet")

# Recently viewed files
result = client.list_recent(mime_type="doc")

# List folder contents
result = client.list_folder("FOLDER_ID")

# Raw query
result = client.search("name contains 'Q1' and trashed = false", page_size=50)

# Get file metadata
metadata = client.get_file("FILE_ID")
print(metadata["name"], metadata["modifiedTime"])
```
