# Google Slides Skill

Command-line interface for reading and editing Google Slides presentations.

## Setup

Uses the same Google OAuth2 credentials as Gmail, Calendar, and Sheets. If you already have `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` in your `.env`, you're ready to go.

### Additional Scope Required

| Scope | Purpose |
|-------|---------|
| `https://www.googleapis.com/auth/presentations` | Read and write Google Slides presentations |

### Configure

```bash
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token
```

## Commands

All commands use `python -m sidekick.clients.gslides`.

### Get Presentation Info

```bash
python -m sidekick.clients.gslides get PRESENTATION_ID
python -m sidekick.clients.gslides get-url "https://docs.google.com/presentation/d/1abc123/edit"
```

Shows presentation metadata:
```
Title: Q1 All-Hands
ID: 1abc123def456
Slides: 12
URL: https://docs.google.com/presentation/d/1abc123def456/edit
```

### List Slides

```bash
python -m sidekick.clients.gslides list-slides PRESENTATION_ID
python -m sidekick.clients.gslides list-slides-url "https://docs.google.com/presentation/d/1abc123/edit"
```

Lists all slides with text preview:
```
  Slide 0: g3ce4afda7_0_0 -- Q1 All-Hands; March 2026
  Slide 1: g3ce4afda7_0_1 -- Agenda; Team updates; Roadmap
  Slide 2: g3ce4afda7_0_2 -- Engineering Highlights
  Slide 3: g3ce4afda7_0_3 -- (empty)
```

### Read All Text

```bash
python -m sidekick.clients.gslides read PRESENTATION_ID
python -m sidekick.clients.gslides read-url "https://docs.google.com/presentation/d/1abc123/edit"
```

Extracts all text from all slides:
```
--- Slide 1 (g3ce4afda7_0_0) ---
Q1 All-Hands
March 2026

--- Slide 2 (g3ce4afda7_0_1) ---
Agenda
Team updates
Roadmap review
```

### Read a Specific Slide

```bash
python -m sidekick.clients.gslides read-slide PRESENTATION_ID SLIDE_ID
python -m sidekick.clients.gslides read-slide-url "https://docs.google.com/presentation/d/1abc123/edit#slide=id.g3ce4afda7_0_2"
```

Shows detailed element-by-element content:
```
Slide: g3ce4afda7_0_2
  [obj_001] TEXT_BOX: Engineering Highlights
  [obj_002] TEXT_BOX: Shipped 3 major features this quarter
  [obj_003] Table:
    | Feature | Status | DRI |
    | Grid V2 | Shipped | Alice |
    | Search | In Progress | Bob |
```

### Replace Text

```bash
python -m sidekick.clients.gslides replace-text PRESENTATION_ID "old text" "new text"
```

Replaces all occurrences of text across the entire presentation.

### Replace Shape Text

```bash
python -m sidekick.clients.gslides replace-shape PRESENTATION_ID OBJECT_ID "new text content"
```

Replaces all text in a specific shape (text box) with new content.

## Python Usage

```python
from sidekick.clients.gslides import GSlidesClient

client = GSlidesClient(
    client_id="your-client-id",
    client_secret="your-client-secret",
    refresh_token="your-refresh-token"
)

# Get presentation
pres = client.get_presentation("1abc123def456")
print(f"{pres['title']} - {len(pres['slides'])} slides")

# List slides with text preview
slides = client.list_slides("1abc123def456")
for s in slides:
    print(f"Slide {s['index']}: {'; '.join(s['texts'][:3])}")

# Read all text
text = client.read_presentation_text("1abc123def456")
print(text)

# Read specific slide elements
slide_data = client.read_slide("1abc123def456", "g3ce4afda7_0_2")
for elem in slide_data["elements"]:
    if elem["type"] == "shape":
        print(f"{elem['objectId']}: {elem['text']}")
    elif elem["type"] == "table":
        for row in elem["rows"]:
            print(" | ".join(row))

# Replace text across presentation
client.replace_text("1abc123def456", "Q1", "Q2")

# Replace all text in a specific shape
client.replace_shape_text("1abc123def456", "obj_001", "New Heading")

# Insert text into a shape
client.insert_text("1abc123def456", "obj_002", "Additional text", insertion_index=0)

# Create a new slide
client.create_slide("1abc123def456", layout="TITLE_AND_BODY")

# Delete a slide
client.delete_slide("1abc123def456", "g3ce4afda7_0_3")

# Extract presentation ID from URL
pres_id = GSlidesClient.extract_presentation_id(
    "https://docs.google.com/presentation/d/1abc123/edit"
)
```
