# Chatwoot Bot & Webhook Integration Guide

Reference for implementing the Lambda bot with Chatwoot webhooks and Agent Bot.

---

## How to use webhooks?

Webhooks are HTTP callbacks set up per account. They are triggered on actions such as message creation. Multiple webhooks can exist for one account.

### How to add a webhook?

1. **Settings → Integrations → Webhooks** → "Configure"
2. "Add new webhook" → Enter **URL** (POST target) and select **events** to subscribe.

Chatwoot sends a **POST** with a JSON payload to the configured URL.

### Sample webhook payload

```json
{
  "event": "message_created",
  "id": "1",
  "content": "Hi",
  "created_at": "2020-03-03 13:05:57 UTC",
  "message_type": "incoming",
  "content_type": "enum",
  "content_attributes": {},
  "source_id": "",
  "sender": {
    "id": "1",
    "name": "Agent",
    "email": "[email protected]"
  },
  "contact": {
    "id": "1",
    "name": "contact-name"
  },
  "conversation": {
    "display_id": "1",
    "additional_attributes": {
      "browser": { ... },
      "referer": "...",
      "initiated_at": "..."
    }
  },
  "account": {
    "id": "1",
    "name": "Chatwoot"
  }
}
```

- **event**: Event name (e.g. `message_created`)
- **message_type**: `incoming` (from user), `outgoing` (from agent), or `template`
- **content_type**: e.g. `input_select`, `cards`, `form`, `text` (default)

### Webhook events (subscribe in dashboard or via API)

| Event | When |
|-------|------|
| `conversation_created` | New conversation |
| `conversation_updated` | Conversation attributes changed |
| `conversation_status_changed` | Status changed (not supported for Agent Bot APIs) |
| `message_created` | Message created |
| `message_updated` | Message updated |
| `webwidget_triggered` | User opened live-chat widget |
| `conversation_typing_on` | Agent started typing |
| `conversation_typing_off` | Agent stopped typing |

### Verifying webhooks (signature)

Chatwoot signs each request. Headers:

- **X-Chatwoot-Signature**: `sha256=<HMAC-SHA256 hex>`
- **X-Chatwoot-Timestamp**: Unix timestamp (seconds)
- **X-Chatwoot-Delivery**: Delivery ID (when available)

**Signature:**

```text
sha256=HMAC-SHA256(webhook_secret, "{timestamp}.{raw_body}")
```

- `raw_body` = raw request body bytes (do not parse/re-serialize for verification).
- Use constant-time comparison (e.g. `hmac.compare_digest`).
- Optionally reject old timestamps (e.g. > 5 minutes) to prevent replay.

**Python verification example:**

```python
import hmac
import hashlib

def verify_signature(raw_body: bytes, timestamp: str, received_signature: str, secret: str) -> bool:
    message = f"{timestamp}.".encode() + raw_body
    expected = "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_signature)
```

---

## How to use Agent bots?

AgentBot connects to an inbox as a bot. New conversations get a "bot" status; Chatwoot sends events to the **bot URL** (webhook), and the bot replies via Chatwoot APIs.

### Typical workflow

1. Bot receives events: `webwidget_triggered`, `message_created`, `message_updated`.
2. Bot processes and generates a response (optionally using Rasa, Dialogflow, Lex, or external APIs).
3. Bot posts reply using Chatwoot APIs (e.g. **message_create**).
4. Bot can set conversation status to **open** to hand off to a human.
5. Bot can keep monitoring open conversations to help agents.

### Human–agent handoff

- With a bot connected, new conversations start as **pending** (bot triages first).
- Bot hands off by calling **conversation update API** to set status to **open**.
- Agents can send back to bot by setting status to **pending** again.

### Creating agent bots

1. **Settings → Bots** → "Add Bot"
2. Set **name**, **avatar**, and **webhook URL** (our Lambda URL).

### Connecting inbox to bot

1. Open the inbox → **Bot Configuration**
2. Select the bot for that inbox → Save
3. Webhook events will be sent to the bot URL for new conversations and messages.

Event details: same as in the [Webhook documentation](#how-to-use-webhooks) above.

---

## Objects (payload structures)

**Account:** `id`, `name`  
**Inbox:** `id`, `name`  
**Contact:** `id`, `name`, `avatar`, `type`, `account`  
**User:** `id`, `name`, `email`, `type`  
**Conversation:** `id`, `inbox_id`, `status`, `messages`, `meta`, `contact_inbox`, etc.  
**Message:** `id`, `content`, `message_type`, `created_at`, `sender`, `conversation`, `inbox`, etc.

---

## Implementation intent

- **Lambda**: Expose an HTTP endpoint (e.g. API Gateway) that receives Chatwoot webhook POSTs.
- **On `message_created`** (and optionally `webwidget_triggered`): Run bot logic and call Chatwoot **message_create** (and optionally **conversation** update) APIs to reply or hand off.
- **Verification**: Validate `X-Chatwoot-Signature` using `X-Chatwoot-Timestamp` and raw body; store webhook secret in env/SSM.
