# Communication Tools (comm)

`tool_genre: "comm"` tools for sending messages and interacting with communication platforms.

These tools are loaded dynamically. Use `comm_control enable` to activate them, or configure your environment to load them at startup.

## Tools

### bluesky

Interact with Bluesky (AT Protocol).

**Environment variables:**
- `UAGENT_BLUESKY_HANDLE` (or `BLUESKY_HANDLE`) — your Bluesky handle (e.g., `user.bsky.social`)
- `UAGENT_BLUESKY_APP_PASSWORD` (or `BLUESKY_APP_PASSWORD`) — an App Password (set in Bluesky Settings > Moderation > App Passwords)

**Actions:**

| action | description | key parameters |
|---|---|---|
| `post` | Create a new text post | `text` (required), `image_path` (optional), `alt` (optional), `lang` (optional, e.g. `ja`, `en`, `zh_CN`, `zh_TW`) |
| `profile` | Get profile info | `actor` (optional, defaults to self) |
| `search` | Search posts | `q` (required), `limit` (default 20) |
| `timeline` | Get home feed | `limit` (default 20) |
| `thread` | Get a post thread | `uri` (required) |
| `like` | Like a post | `uri` (required), `cid` (required) |
| `notifications` | List notifications | `limit` (default 20) |

**Common parameters:**
- `output_format`: `json` (default) or `text`
- `save_images`: `true` to download images from posts and open with default app (CLI only)

**Examples:**
```
bluesky action="post" text="Hello from uag!"
bluesky action="post" text="Cat photo" image_path="C:/cat.jpg" alt="A cute cat"
bluesky action="search" q="uag agent" limit=5
bluesky action="timeline" save_images=true
bluesky action="notifications"
```

### discord_channel

Send messages to and read messages from Discord channels using a bot token.

**Environment variables:**
- `DISCORD_BOT_TOKEN` — Discord bot token

**Actions:**

| action | description | key parameters |
|---|---|---|
| `send` | Send a message to a channel | `channel_id` (required), `message` (required) |
| `send_and_wait` | Send a message and wait for a reply | `channel_id` (required), `message` (required), `wait` (default 30s) |
| `history` | Read recent messages from a channel | `channel_id` (required), `limit` (default 10) |

**Examples:**
```
discord_channel_chat action="send" channel_id="123456789" message="Hello from uag!"
discord_channel_chat action="history" channel_id="123456789" limit=5
```

### teams_webhook

Post messages to Microsoft Teams via an Incoming Webhook URL.

**Environment variables:**
- `TEAMS_WEBHOOK_URL` — Teams Incoming Webhook URL

**Actions:**

| action | description | key parameters |
|---|---|---|
| `post` | Post a message to Teams | `message` (required) |
| `post_card` | Post a card with title and image | `message` (required), `title`, `summary`, `image_url` |

**Examples:**
```
teams_webhook_post action="post" message="Build completed successfully."
teams_webhook_post action="post_card" message="Release v1.2.3" title="New Release" summary="Bug fixes and improvements"
```

## Enabling comm tools

By default, comm tools are disabled. To enable them:

```
comm_control enable
```

To disable:

```
comm_control disable
```

You can also set the following in your environment to auto-load them:

```
UAGENT_COMM_ENABLED=1
```

## Common notes

- All comm tools respect the `output_format` parameter (`json` / `text`).
- Credentials are loaded from environment variables. Do not hardcode tokens.
- For Bluesky, always use an App Password, not your main account password.
- For Discord, the bot must be added to the target server with appropriate permissions.
- For Teams, the webhook URL can be created from Teams Channel Connectors settings.

### gmail_send

Send an email via Gmail SMTP using App Password.

**Environment variables:**
- `UAGENT_GMAIL_ADDRESS` — your Gmail address (e.g., `user@gmail.com`)
- `UAGENT_GMAIL_APP_PASSWORD` — an App Password (create at https://myaccount.google.com/apppasswords)

**Parameters:**

| parameter | required | description |
|---|---|---|
| `to` | yes | Recipient email address(es). Comma-separated for multiple. |
| `subject` | yes | Email subject. |
| `body` | yes | Email body text (plain text). |
| `cc` | no | CC recipient email address(es). Comma-separated. |
| `bcc` | no | BCC recipient email address(es). Comma-separated. |
| `html` | no | If true, body is treated as HTML. Default: false. |

**Examples:**
```
gmail_send to="user@example.com" subject="Hello" body="Test message"
gmail_send to="a@b.com,c@d.com" subject="Report" body="<h1>Report</h1>" html=true
```

### gmail_read

Read/search Gmail inbox via IMAP.

**Environment variables:**
- `UAGENT_GMAIL_ADDRESS` — your Gmail address
- `UAGENT_GMAIL_APP_PASSWORD` — an App Password

**Actions:**

| action | description | key parameters |
|---|---|---|
| `list` | Recent inbox messages | `max_results` (default 10, max 50) |
| `search` | Search by IMAP query | `query` (required), `max_results` |
| `read` | Read full message body | `message_id` (required, from list/search result) |
| `unread` | Unread messages only | `max_results` |

**Examples:**
```
gmail_read action="list" max_results=5
gmail_read action="search" query="SUBJECT hello"
gmail_read action="read" message_id="123456"
gmail_read action="unread"
```

## See also

- [IOT_USECASE.md](IOT_USECASE.md) — for IoT-related tools (SwitchBot, ECHONET Lite, Matter, UPnP)
