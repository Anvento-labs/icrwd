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
CHATWOOT_BOT_TOKEN = os.environ.get("CHATWOOT_BOT_TOKEN", "xTp1he5yEqk81dzKzb4NNfUe") 
CHATWOOT_USER_TOKEN = os.environ.get("CHATWOOT_USER_TOKEN", "MDrsGNERoskafLdnYzVB8KR2")

DEFAULT_ASSIGNEE_ID = 1

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
        return _http(200, json.dumps({"status": "missing data"}))

    headers_for_bot = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_BOT_TOKEN,
    }
    
    headers_for_admin = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_USER_TOKEN, 
    }

    logger.info("Sending interim processing bubble...")
    interim_response = _chatwoot_request(
        "POST", CHATWOOT_BASE_URL, account_id, conversation_id, "messages",
        {"content": "Thinking...", "message_type": "outgoing"},
        headers_for_bot
    )
    
    interim_message_id = interim_response.get("id") if interim_response else None

    try:
        logger.info(f"Invoking LangGraph with question: {content}")
        final_state = app_graph.invoke({"question": content})
        bot_response = final_state.get("generation", "I am having trouble processing that.")
    except Exception as e:
        logger.error(f"LangGraph execution error: {e}")
        bot_response = "Sorry, my systems are experiencing a temporary error."

    handoff_keywords = ["transferring", "human agent", "flagged your conversation", "escalating"]
    is_handoff = any(keyword in bot_response.lower() for keyword in handoff_keywords)

    if interim_message_id:
        logger.info(f"Deleting interim message {interim_message_id}...")
        _chatwoot_request(
            "DELETE", CHATWOOT_BASE_URL, account_id, conversation_id, f"messages/{interim_message_id}",
            None, headers_for_admin
        )

    _chatwoot_request(
        "POST", CHATWOOT_BASE_URL, account_id, conversation_id, "messages",
        {"content": bot_response, "message_type": "outgoing"},
        headers_for_bot
    )

    if is_handoff:
        logger.info("Handoff triggered. Opening and assigning conversation.")
        
        _chatwoot_request(
            "POST", CHATWOOT_BASE_URL, account_id, conversation_id, "toggle_status",
            {"status": "open"}, headers_for_bot
        )
        
        _chatwoot_request(
            "POST", CHATWOOT_BASE_URL, account_id, conversation_id, "assignments",
            {"assignee_id": DEFAULT_ASSIGNEE_ID}, headers_for_admin
        )

    return _http(200, json.dumps({"status": "success"}))


def _chatwoot_request(method, base_url, account_id, conversation_id, endpoint, data, headers):
    """
    A generic request handler that supports POST and DELETE methods, 
    and returns the JSON response from Chatwoot.
    """
    url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/{endpoint}"
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data else None,
        headers=headers,
        method=method,
    )
    
    try:
        response = urllib.request.urlopen(req)
        response_body = response.read().decode('utf-8')
        return json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as e:
        logger.error(f"Chatwoot API error {e.code}: {e.read()}")
        return None
    except urllib.error.URLError as e:
        logger.error(f"Chatwoot API URLError: {e.reason}")
        return None


def _http(status_code, body):
    """Standardizes the HTTP response back to AWS Lambda URL/API Gateway."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": body,
    }