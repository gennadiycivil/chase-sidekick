---
name: study-style
description: Study writing style from Google Drive docs, Dropbox Paper docs, and Slack messages, then save observations to memory
argument-hint: [source: all|gdrive|dropbox|slack]
allowed-tools: Bash, Read, Write
---

# Study Writing Style Agent

Analyze the user's writing style across Google Drive, Dropbox Paper, and Slack messages. Save detailed observations to `memory/writing-style.md`.

## Overview

This agent:
1. Pulls documents the user authored from Google Drive, Dropbox, and Slack
2. Reads content from each source
3. Analyzes writing patterns (tone, structure, vocabulary, formatting)
4. Saves a comprehensive style guide to memory

## Step 1: Gather Google Drive Documents

Search for documents owned by the user (most recent first):

```bash
# Get recent Google Docs owned by user
python -m sidekick.clients.gdrive mine "" doc
```

For each document found, read its content:

```bash
# Extract document ID from the URL, then read
python -m sidekick.clients.gdocs read <document_id>
```

Focus on:
- 1:1 meeting notes (show interpersonal communication style)
- Planning docs (show strategic/analytical writing)
- Status reports (show professional summary style)
- Any docs the user authored directly

Read at least 10-15 documents for a good sample. Save raw content to temp files:

```bash
mkdir -p /tmp/style_study
# Save each doc to a temp file
python -m sidekick.clients.gdocs read <doc_id> > /tmp/style_study/gdoc_<name>.txt
```

## Step 2: Gather Dropbox Paper Documents

Search for Paper docs:

```bash
# Search for Paper docs
python -m sidekick.clients.dropbox search "" --cat paper

# List Paper Docs folder
python -m sidekick.clients.dropbox ls "/Paper Docs"
```

For each Paper doc found, read its content:

```bash
python -m sidekick.clients.dropbox get-paper-contents "<path>"
```

Focus on the same categories as Google Docs. Save to temp files:

```bash
python -m sidekick.clients.dropbox get-paper-contents "<path>" > /tmp/style_study/paper_<name>.txt
```

## Step 3: Gather Slack Messages

Search for messages the user sent in key channels:

```bash
# Search for messages from the user
python -m sidekick.clients.slack search "from:me" --count 100

# Also try specific channels where the user posts
python -m sidekick.clients.slack search "from:me in:#general" --count 50
python -m sidekick.clients.slack search "from:me in:#team" --count 50
```

Save to temp files:

```bash
python -m sidekick.clients.slack search "from:me" --count 100 > /tmp/style_study/slack_messages.txt
```

## Step 4: Analyze Writing Patterns

Read all gathered content and analyze the following dimensions:

### Tone & Voice
- Formal vs. casual register
- Use of humor, directness, hedging
- First person vs. third person
- Active vs. passive voice

### Structure & Organization
- How they start documents (jump in vs. context-setting)
- Use of headers, bullets, numbered lists
- Paragraph length and density
- How they organize meeting notes (chronological, by topic, etc.)

### Vocabulary & Phrasing
- Common phrases and expressions they use repeatedly
- Technical jargon level
- Transition words they favor
- How they frame requests, feedback, and decisions

### Formatting Preferences
- Markdown style (bold, italic, code blocks)
- Bullet point style (dashes vs. asterisks, nesting depth)
- Use of links, @mentions, emojis
- How they format action items

### Communication Context Differences
- How their style varies between:
  - 1:1 notes (personal, direct)
  - Team updates (broadcast, informational)
  - Planning docs (analytical, strategic)
  - Slack messages (quick, informal)

## Step 5: Write Style Guide

Create `memory/writing-style.md` with the analysis results.

Format the file as:

```markdown
# Writing Style Guide

Generated: YYYY-MM-DD
Sources analyzed: N Google Docs, N Paper docs, N Slack messages

## Voice & Tone
[observations]

## Structure Patterns
[observations]

## Common Phrases & Vocabulary
[list of recurring phrases with examples]

## Formatting Conventions
[observations]

## Context-Specific Styles
### 1:1 Notes
[observations]
### Status Updates
[observations]
### Planning Documents
[observations]
### Slack Messages
[observations]

## Example Snippets
[3-5 representative excerpts that capture the style]

## Style Rules for Mimicry
[Concise rules an AI should follow to match this style]
```

## Step 6: Clean Up

```bash
rm -rf /tmp/style_study
```

## Tips

- **Quantity**: Aim for at least 20 documents total across all sources
- **Recency**: Prioritize recent documents (last 3 months) as style evolves
- **Variety**: Get samples from different contexts (1:1s, reports, Slack)
- **Quotes**: Include actual phrases and sentences as examples in the style guide
- **Be specific**: "Uses dashes for bullets, not asterisks" is better than "casual formatting"
- **Source argument**: If user passes `gdrive`, `dropbox`, or `slack`, only analyze that source. Default `all` analyzes everything.
