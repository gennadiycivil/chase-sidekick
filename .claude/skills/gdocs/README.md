# Google Docs Skill

Command-line interface for Google Docs operations: read, create, and write documents with markdown formatting.

## Setup

Uses the same Google OAuth2 credentials as Gmail, Calendar, and Sheets. If you already have `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` in your `.env`, you're ready to go.

### Additional Scope Required

When creating your OAuth2 credentials, ensure the following scope is included:

| Scope | Purpose |
|-------|---------|
| `https://www.googleapis.com/auth/documents` | Read and write Google Docs |

If you already have Google credentials configured for other skills, you may need to re-authorize with the additional scope.

### Configure

```bash
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token
```

## Commands

All commands use `python -m sidekick.clients.gdocs`.

### Create Document

```bash
python -m sidekick.clients.gdocs create "My New Document"
```

Creates a new empty Google Doc:
```
Created: My New Document
ID: 1abc123def456
URL: https://docs.google.com/document/d/1abc123def456/edit
```

### Create from Markdown

```bash
python -m sidekick.clients.gdocs create-from-md "Sprint Report" report.md
```

Creates a new Google Doc from a local markdown file with formatting (headings, bold, bullets):
```
Created: Sprint Report
ID: 1abc123def456
URL: https://docs.google.com/document/d/1abc123def456/edit
```

### Read Document

```bash
python -m sidekick.clients.gdocs read 1abc123def456
python -m sidekick.clients.gdocs read-url "https://docs.google.com/document/d/1abc123def456/edit"
```

Reads document content as plain text (including table content).

### Get Document Metadata

```bash
python -m sidekick.clients.gdocs get 1abc123def456
```

Shows document metadata:
```
Title: Sprint Report
ID: 1abc123def456
URL: https://docs.google.com/document/d/1abc123def456/edit
```

## Python Usage

```python
from sidekick.clients.gdocs import GDocsClient

client = GDocsClient(
    client_id="your-client-id",
    client_secret="your-client-secret",
    refresh_token="your-refresh-token"
)

# Read a document as plain text
text = client.read_document("1abc123def456")

# Read by URL
doc_id = GDocsClient.extract_document_id("https://docs.google.com/document/d/1abc123def456/edit")
text = client.read_document(doc_id)

# Create a new document
result = client.create_document("My Document")
print(result["url"])

# Create from markdown with formatting
result = client.create_from_markdown("Sprint Report", "# Heading\n- Bullet 1\n- Bullet 2")

# Insert text at a position
client.insert_text("1abc123def456", "Hello world\n", index=1)

# Batch update (advanced)
client.batch_update("1abc123def456", [
    {"insertText": {"location": {"index": 1}, "text": "New text\n"}}
])
```
