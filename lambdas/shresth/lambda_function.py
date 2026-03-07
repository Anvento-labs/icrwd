import json
import base64
import os
import urllib.request
import urllib.error
import logging
from app.graph import app_graph 

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHATWOOT_BASE_URL = os.environ.get("CHATWOOT_BASE_URL", "http://44.215.200.55:3000").rstrip("/")
CHATWOOT_BOT_TOKEN = os.environ.get("CHATWOOT_BOT_TOKEN", "pssyUeBpYN54K9iJdksW3UEd") 
CHATWOOT_USER_TOKEN = os.environ.get("CHATWOOT_USER_TOKEN", "Ey7U2scnyhg1T8t9midZHTrv")
DEFAULT_ASSIGNEE_ID=1 

def lambda_handler(event, context):
    logger.info("Webhook received.")

    try:
        body = event.get("body") or ""
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        payload = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse event body: {e}")
        return _http(400, json.dumps({"error": "Invalid JSON"}))

    event_name = payload.get("event")
    message_type = payload.get("message_type")
    
    if event_name != "message_created" or message_type != "incoming":
        logger.info("Ignored non-incoming message or non-message event.")
        return _http(200, json.dumps({"status": "ignored"}))

    content = (payload.get("content") or "").strip()
    conversation = payload.get("conversation") or {}
    account = payload.get("account") or {}
    account_id = account.get("id")
    conversation_id = conversation.get("id")

    if not content or account_id is None or conversation_id is None:
        logger.warning("Missing message content or conversation ID.")
        return _http(200, json.dumps({"status": "missing data"}))

    headers_for_bot = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_BOT_TOKEN,
    }
    
    headers_for_admin = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_USER_TOKEN, 
    }

    logger.info("Sending interim processing message...")
    _chatwoot_post(
        CHATWOOT_BASE_URL, account_id, conversation_id, None, "messages",
        {"content": "Give me just a moment while I check the records for you...", "message_type": "outgoing"},
        headers_for_bot
    )

    try:
        logger.info(f"Invoking LangGraph with question: {content}")
        final_state = app_graph.invoke({"question": content})
        bot_response = final_state.get("generation", "I am having trouble processing that.")
    except Exception as e:
        logger.error(f"LangGraph execution error: {e}")
        bot_response = "Sorry, my systems are experiencing a temporary error."

    handoff_keywords = ["transferring", "human agent", "flagged your conversation", "escalating"]
    is_handoff = any(keyword in bot_response.lower() for keyword in handoff_keywords)

    _chatwoot_post(
        CHATWOOT_BASE_URL, account_id, conversation_id, None, "messages",
        {"content": bot_response, "message_type": "outgoing"},
        headers_for_bot
    )

    if is_handoff:
        logger.info("Handoff triggered. Opening and assigning conversation for human agents.")
        
        _chatwoot_post(
            CHATWOOT_BASE_URL, account_id, conversation_id, "toggle_status", None,
            {"status": "open"},
            headers_for_bot
        )
        
        _chatwoot_post(
            CHATWOOT_BASE_URL, account_id, conversation_id, "assignments", None,
            {"assignee_id": DEFAULT_ASSIGNEE_ID},
            headers_for_admin
        )

    return _http(200, json.dumps({"status": "success"}))


def _chatwoot_post(base_url, account_id, conversation_id, path_suffix, path_key, data, headers):
    """
    Unified function that decides the Chatwoot URL based on suffix/key.
    Uses urllib to avoid heavy external dependencies like 'requests'.
    """
    if path_suffix:
        url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/{path_suffix}"
    else:
        url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/{path_key}"
        
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        logger.error(f"Chatwoot API error {e.code}: {e.read()}")
    except urllib.error.URLError as e:
        logger.error(f"Chatwoot API URLError: {e.reason}")


def _http(status_code, body):
    """Standardizes the HTTP response back to AWS Lambda URL/API Gateway."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": body,
    }