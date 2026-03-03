# Gmail Skill

Search and manage Gmail messages using the command line.

## Setup

Gmail, Google Calendar, and Google Sheets all share the same OAuth2 credentials. You only need to do this once — the same `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` in your `.env` file work for all three services.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top and click **New Project**
3. Give it a name (e.g., "Sidekick") and click **Create**
4. Make sure the new project is selected in the dropdown

### Step 2: Enable the APIs

1. Go to **APIs & Services > Library** in the left sidebar
2. Search for and enable each of these:
   - **Gmail API**
   - **Google Calendar API**
   - **Google Sheets API**
   - **Google Drive API**

### Step 3: Create OAuth2 Credentials

1. Go to **APIs & Services > Credentials**
2. Click **+ Create Credentials > OAuth client ID**
3. If prompted to configure a consent screen first:
   - Choose **External** (or **Internal** if you're on Google Workspace)
   - Fill in the required fields (app name, your email)
   - Add your email as a test user
   - Save and continue through the screens
4. Back in Credentials, click **+ Create Credentials > OAuth client ID**
5. Application type: **Desktop app**
6. Give it a name and click **Create**
7. Copy the **Client ID** and **Client Secret** shown in the dialog

### Step 4: Generate a Refresh Token

Run the included helper script:

```bash
python3 tools/get_google_refresh_token.py
```

The script will:
1. Ask you to paste your Client ID and Client Secret
2. Open your browser to authorize the app with your Google account
3. After you authorize, you'll be redirected to a `localhost` URL that won't load — this is expected
4. Copy the **entire URL** from your browser's address bar and paste it back into the script
5. The script outputs your refresh token

**Tip:** If you've previously authorized this app and don't get a refresh token, go to https://myaccount.google.com/permissions, remove the app, and run the script again.

### Step 5: Configure .env

Add (or update) these three lines in your `.env` file:

```bash
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REFRESH_TOKEN=your_refresh_token_here
```

### Step 6: Verify

```bash
python -m sidekick.clients.gmail search "is:unread"
```

If you see your unread messages, you're all set.

## Commands

### Search Messages

Search for messages using Gmail search syntax:

```bash
# Search from specific sender
python -m sidekick.clients.gmail search "from:someone@example.com"

# Search by subject
python -m sidekick.clients.gmail search "subject:meeting"

# Search unread messages
python -m sidekick.clients.gmail search "is:unread"

# Search with date filter
python -m sidekick.clients.gmail search "after:2024/01/01"

# Combine filters
python -m sidekick.clients.gmail search "from:boss@company.com is:unread" 5

# Search in specific folder
python -m sidekick.clients.gmail search "in:inbox is:starred"
```

**Output format** (one line per message):
```
18f2c4e5a1b2c3d4: John Doe <john@example.com> - Weekly Meeting
  Let's schedule our weekly sync for next Tuesday...
```

### Get Full Message

Get complete details of a specific message:

```bash
python -m sidekick.clients.gmail get MESSAGE_ID
```

**Output includes:**
- Message and thread IDs
- From, To, Subject, Date headers
- Full message body (plain text)

Example:
```
Message ID: 18f2c4e5a1b2c3d4
Thread ID: 18f2c4e5a1b2c3d4
From: John Doe <john@example.com>
To: you@example.com
Subject: Weekly Meeting
Date: Mon, 15 Jan 2024 10:30:00 -0800

Body:
--------------------------------------------------------------------------------
Let's schedule our weekly sync for next Tuesday at 2pm.

Best,
John
--------------------------------------------------------------------------------
```

### Create Draft Email

Create a draft email (does not send):

```bash
python -m sidekick.clients.gmail create-draft "recipient@example.com" "Subject" "Body text"
```

Example:
```bash
python -m sidekick.clients.gmail create-draft \
  "team@example.com" \
  "Sprint Planning" \
  "Hi team, let's meet tomorrow to plan the next sprint."
```

**Output:**
```
Draft created successfully!
Draft ID: r-1234567890
Message ID: 18f2c4e5a1b2c3d4
```

## Python Usage

```python
from sidekick.clients.gmail import GmailClient

client = GmailClient(
    client_id="your_client_id",
    client_secret="your_client_secret",
    refresh_token="your_refresh_token"
)

# Search messages
messages = client.search_messages("from:boss@example.com", max_results=5)
for msg in messages:
    headers = client.get_message_headers(msg)
    print(f"From: {headers['from']}")
    print(f"Subject: {headers['subject']}")

# Get full message
message = client.get_message("MESSAGE_ID")
body = client.get_message_body(message)
print(body)

# Create draft
draft = client.create_draft(
    to="recipient@example.com",
    subject="Hello",
    body="This is a draft email",
    cc="cc@example.com"  # optional
)
print(f"Draft ID: {draft['id']}")
```

## Gmail Search Syntax

Common search operators:

- `from:sender@example.com` - Messages from specific sender
- `to:recipient@example.com` - Messages to specific recipient
- `subject:keyword` - Messages with keyword in subject
- `is:unread` - Unread messages
- `is:starred` - Starred messages
- `is:important` - Important messages
- `has:attachment` - Messages with attachments
- `after:2024/01/01` - Messages after date
- `before:2024/12/31` - Messages before date
- `newer_than:7d` - Messages from last 7 days
- `older_than:30d` - Messages older than 30 days
- `in:inbox` - Messages in inbox
- `in:sent` - Sent messages
- `label:work` - Messages with label "work"

Combine with AND (space) or OR:
- `from:john subject:meeting` - Both conditions
- `from:john OR from:jane` - Either condition

## Limitations

- Draft creation does NOT send emails (by design)
- Plain text emails only (no HTML formatting)
- No attachment support in current version
- Requires OAuth2 setup (one-time process)

## Troubleshooting

**"Failed to refresh access token"**
- Verify your client_id and client_secret are correct
- Ensure refresh_token is valid (may need to regenerate)
- Check that Gmail API is enabled in Google Cloud Console

**"403 Forbidden"**
- Ensure Gmail API is enabled for your project
- Check OAuth2 scopes include `gmail.modify`

**"401 Unauthorized"**
- Your refresh token may have expired or been revoked
- Regenerate the refresh token using the setup script
