import json
import base64
import os
import urllib.request
import urllib.error
import logging
import boto3
from app.graph import app_graph

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHATWOOT_BASE_URL = os.environ.get("CHATWOOT_BASE_URL", "http://44.215.200.55:3000").rstrip("/")
CHATWOOT_BOT_TOKEN = os.environ.get("CHATWOOT_BOT_TOKEN", "xTp1he5yEqk81dzKzb4NNfUe")
CHATWOOT_USER_TOKEN = os.environ.get("CHATWOOT_USER_TOKEN", "MDrsGNERoskafLdnYzVB8KR2")
DEFAULT_ASSIGNEE_ID = 1


def lambda_handler(event, context):

    # ── PHASE 2: background worker (invoked async by Phase 1) ──────────────
    if event.get("is_background_worker"):
        return _process_ai_in_background(event.get("payload", {}))

    # ── PHASE 1: greeter — parse webhook, spawn worker, return 200 fast ────
    try:
        body = event.get("body") or ""
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        payload = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse body: {e}")
        return _http(400, json.dumps({"error": "Invalid JSON"}))

    event_name   = payload.get("event")
    message_type = payload.get("message_type")

    if event_name != "message_created" or message_type != "incoming":
        return _http(200, json.dumps({"status": "ignored"}))

    content         = (payload.get("content") or "").strip()
    account_id      = (payload.get("account") or {}).get("id")
    conversation_id = (payload.get("conversation") or {}).get("id")

    if not content or account_id is None or conversation_id is None:
        return _http(200, json.dumps({"status": "missing data"}))

    logger.info(f"👋 GREETER: spawning background worker for conversation {conversation_id}")

    try:
        boto3.client("lambda").invoke(
            FunctionName=context.function_name,
            InvocationType="Event",
            Payload=json.dumps({
                "is_background_worker": True,
                "payload": payload
            })
        )
    except Exception as e:
        logger.error(f"❌ Failed to spawn worker (check IAM lambda:InvokeFunction permission): {e}")

    return _http(200, json.dumps({"status": "processing"}))


def _process_ai_in_background(payload):
    logger.info("⚙️ WORKER: starting AI processing...")

    content         = (payload.get("content") or "").strip()
    account_id      = (payload.get("account") or {}).get("id")
    conversation_id = (payload.get("conversation") or {}).get("id")

    logger.info(f"⚙️ account={account_id}, conversation={conversation_id}, content='{content}'")

    headers_admin = {"Content-Type": "application/json", "api_access_token": CHATWOOT_USER_TOKEN}

    # Turn on typing indicator
    _chatwoot_request("POST", account_id, conversation_id, "toggle_typing_status",
                      {"typing_status": "on"}, headers_admin)

    try:
        logger.info("⚙️ Invoking LangGraph...")
        final_state  = app_graph.invoke({"question": content})
        bot_response = final_state.get("generation", "I am having trouble processing that.")
        logger.info(f"⚙️ LangGraph response: '{bot_response[:120]}'")
    except Exception as e:
        logger.error(f"❌ LangGraph error: {e}")
        bot_response = "Sorry, my systems are experiencing a temporary error."

    handoff_keywords = ["transferring", "human agent", "flagged your conversation", "escalating"]
    is_handoff = any(kw in bot_response.lower() for kw in handoff_keywords)

    # Turn off typing indicator
    _chatwoot_request("POST", account_id, conversation_id, "toggle_typing_status",
                      {"typing_status": "off"}, headers_admin)

    # ✅ Post the AI reply — message_type MUST be integer 1, not string "outgoing"
    result = _chatwoot_request("POST", account_id, conversation_id, "messages", {
        "content":      bot_response,
        "message_type": 1,
        "private":      False
    }, headers_admin)

    if result:
        logger.info(f"✅ WORKER: message posted, ID={result.get('id')}")
    else:
        logger.error("❌ WORKER: failed to post message — see Chatwoot error above")

    if is_handoff:
        logger.info("🔀 Handoff triggered — assigning to human agent")
        _chatwoot_request("POST", account_id, conversation_id, "toggle_status",
                          {"status": "open"}, headers_admin)
        _chatwoot_request("POST", account_id, conversation_id, "assignments",
                          {"assignee_id": DEFAULT_ASSIGNEE_ID}, headers_admin)

    logger.info("⚙️ WORKER: done.")
    return True


def _chatwoot_request(method, account_id, conversation_id, endpoint, data, headers):
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/conversations/{conversation_id}/{endpoint}"
    logger.info(f"→ {method} {url}")

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data else None,
        headers=headers,
        method=method,
    )
    try:
        response      = urllib.request.urlopen(req)
        response_body = response.read().decode("utf-8")
        parsed        = json.loads(response_body) if response_body else {}
        logger.info(f"← {response.status} | id={parsed.get('id', 'n/a')}")
        return parsed
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error(f"← HTTP {e.code} on /{endpoint}: {error_body}")
        return None
    except urllib.error.URLError as e:
        logger.error(f"← URLError on /{endpoint}: {e.reason}")
        return None


def _http(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": body,
    }