# Slack Skill

Command-line interface for Slack operations.

## Setup

### Step 1: Create a Slack App

1. Go to https://api.slack.com/apps and click **Create New App**
2. Choose **From scratch**
3. Enter an app name (e.g., "Sidekick") and select your workspace
4. Fill in the **Short Description** and **Long Description** (long description must be 175+ characters)
5. Click **Create App**

### Step 2: Add Bot Token Scopes

1. In the left sidebar, click **OAuth & Permissions**
2. Scroll to **Bot Token Scopes** and add these scopes:

| Scope | Purpose |
|-------|---------|
| `channels:read` | List public channels and their metadata |
| `channels:history` | Read messages in public channels the bot is a member of |
| `groups:read` | List private channels the bot has been invited to |
| `groups:history` | Read messages in private channels |
| `users:read` | Resolve user IDs to display names |
| `users:read.email` | Display email alongside names for identification |
| `chat:write` | Send messages (optional, only for send-message command) |

### Step 3: Enterprise Workspace Approval

For enterprise workspaces, the app must be approved before installation.

1. On the **OAuth & Permissions** page, click **Request to Install** (or **Install to Workspace** if no approval is required)
2. Enter a message for admins explaining the app's purpose
3. The admin team will respond with an approval process

**Typical enterprise approval requires a support ticket with:**

- **Business justification** — What the app is for and who uses it
- **What data will be accessed** — Message content, channel metadata, user profiles
- **Why each scope is required** — One-line justification per scope
- **Data storage / retention** — Where data goes and how long it's kept
- **Who will have access** — Which people or systems use the token

**Suggested responses for a personal EM productivity tool:**

- **Business justification**: Personal CLI tool to read channel conversations for meeting prep and cross-team awareness. Single user, not distributed.
- **Data accessed**: Message content/metadata from channels the bot is invited to. User profiles for name resolution.
- **Data storage**: No data stored, persisted, or exported. Fetched on-demand, displayed in terminal, discarded on session end.
- **Access**: Only me. Token stored in local .env file, gitignored, never shared.

### Step 4: Install and Get Token

Once approved:

1. Go to **OAuth & Permissions** in the left sidebar
2. Click **Install to Workspace** and authorize
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### Step 5: Configure

Add the token to your `.env` file in the project root:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
```

### Step 6: Invite Bot to Channels

The bot can only read channels it has been explicitly invited to.

In Slack, go to each channel you want to read and type:

```
/invite @Sidekick
```

### Step 7: Verify

```bash
python -m sidekick.clients.slack list-channels
python -m sidekick.clients.slack history C0EXAMPLE1 --limit 5
```

## Commands

All commands use the module form (`python -m sidekick.clients.slack`).

### List Channels

```bash
python -m sidekick.clients.slack list-channels
```

Lists all channels the bot has access to:
```
Found 15 channels:
#general (42 members) [Team announcements]
#engineering (28 members) [Engineering discussion]
#random (35 members)
```

### Get Channel Info

```bash
python -m sidekick.clients.slack channel-info C0EXAMPLE1
```

Shows detailed channel information:
```
#engineering
  Members: 28
  Topic: Engineering discussion
  Purpose: For engineering team conversations
  ID: C0EXAMPLE1
```

### Get Channel History

```bash
python -m sidekick.clients.slack history C0EXAMPLE1
python -m sidekick.clients.slack history C0EXAMPLE1 --limit 50
```

Shows recent messages with user names resolved:
```
Last 100 messages:
[2026-03-01 10:30] Alice Smith: Good morning team!
[2026-03-01 10:32] Bob Jones: Morning! Ready for standup?
[2026-03-01 10:35] Alice Smith: Let's do it
```

### Get Thread Replies

```bash
python -m sidekick.clients.slack thread C0EXAMPLE1 1709312200.123456
```

Shows all replies in a thread:
```
Thread (3 messages):
[2026-03-01 10:30] Alice Smith: Should we update the API?
[2026-03-01 10:32] Bob Jones: Yes, let's do v2
[2026-03-01 10:35] Charlie Brown: +1
```

### List Users

```bash
python -m sidekick.clients.slack users
```

Lists active, non-bot users:
```
Found 50 users:
@alice (Alice Smith) [alice@example.com]
@bob (Bob Jones) [bob@example.com]
```

### Get User Info

```bash
python -m sidekick.clients.slack user-info U0EXAMPLE1
```

Shows detailed user information:
```
@alice
  Name: Alice Smith
  Title: Senior Engineer
  Email: alice@example.com
  ID: U0EXAMPLE1
```

### Send Message

```bash
python -m sidekick.clients.slack send-message C0EXAMPLE1 "Hello team!"
```

Sends a message to a channel. **Note**: Always confirm with the user before sending messages.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `not_in_channel` | Bot hasn't been invited to the channel | `/invite @Sidekick` in the channel |
| `invalid_auth` | Token is wrong or expired | Regenerate token at api.slack.com/apps |
| `missing_scope` | App doesn't have the required permission | Add the scope in OAuth & Permissions, reinstall |
| `channel_not_found` | Channel ID is wrong or bot can't see it | Verify channel ID from Slack URL |
| `ratelimited` | Too many API calls | Wait and retry; reduce --limit |

## Python Usage

```python
from sidekick.clients.slack import SlackClient

client = SlackClient(bot_token="xoxb-your-token")

# List channels
channels = client.list_channels()
for ch in channels:
    print(f"#{ch['name']} ({ch['num_members']} members)")

# Get channel history
messages = client.get_channel_history("C0EXAMPLE1", limit=50)
for msg in messages:
    print(f"{msg['user']}: {msg['text']}")

# Get thread replies
replies = client.get_thread_replies("C0EXAMPLE1", "1709312200.123456")

# Get user info
user = client.get_user_info("U0EXAMPLE1")
print(user["real_name"])

# Send a message
client.send_message("C0EXAMPLE1", "Hello from Sidekick!")
```
