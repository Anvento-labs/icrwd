import json
import base64
import os
import logging

from app.graphs.orchestrate_graph import app_graph
from app.tools.chatwoot_tool import send_message, delete_message, toggle_status, assign_agent
from app.tools import mongo_tool

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHATWOOT_BASE_URL = os.environ.get("CHATWOOT_BASE_URL", "http://44.215.200.55:3000").rstrip("/")
CHATWOOT_BOT_TOKEN = os.environ.get("CHATWOOT_BOT_TOKEN", "")
CHATWOOT_USER_TOKEN = os.environ.get("CHATWOOT_USER_TOKEN", "")
DEFAULT_ASSIGNEE_ID = int(os.environ.get("DEFAULT_ASSIGNEE_ID", "1"))
# Hardcoded lookup for context user (email or phone) — loaded into state before graph runs
HARDCODED_USER_IDENTIFIER = os.environ.get(
    "SUPPORT_CONTEXT_USER_EMAIL",
    "android.user@yopmail.com",
)


def lambda_handler(event, context):
    logger.info("Webhook received.")

    # --- Parse webhook body ---
    try:
        body = event.get("body") or ""
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        payload = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse body: {e}")
        return _http(400, {"error": "Invalid JSON"})

    event_name = payload.get("event")
    message_type = payload.get("message_type")

    if event_name != "message_created" or message_type != "incoming":
        return _http(200, {"status": "ignored"})

    content = (payload.get("content") or "").strip()
    conversation = payload.get("conversation") or {}
    account = payload.get("account") or {}
    account_id = account.get("id")
    conversation_id = conversation.get("id")

    if not content or account_id is None or conversation_id is None:
        return _http(200, {"status": "missing data"})

    bot_headers = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_BOT_TOKEN,
    }
    admin_headers = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_USER_TOKEN,
    }

    # --- Send interim "Thinking..." bubble ---
    interim = send_message(CHATWOOT_BASE_URL, account_id, conversation_id, "Thinking...", bot_headers)
    interim_id = interim.get("id") if interim else None

    # --- Invoke LangGraph ---
    try:
        logger.info(f"Invoking graph for: {content[:100]}")
        context_user = mongo_tool.get_user_info(HARDCODED_USER_IDENTIFIER) or {}
        logger.info(f"Loaded user for graph context: {context_user}")
        final_state = app_graph.invoke({
            "message": content,
            "messages": [],
            "session_id": str(conversation_id),
            "previous_node": None,
            "next": "",
            "persona": "",
            "plan": "",
            "reply": "",
            "handoff": False,
            "user": context_user,
        })
        reply = final_state.get("reply") or "I'm having trouble processing that right now."
        is_handoff = final_state.get("handoff", False)
    except Exception as e:
        logger.error(f"Graph execution error: {e}")
        reply = "Sorry, I'm experiencing a temporary issue. Please try again shortly."
        is_handoff = False

    # --- Delete interim message ---
    if interim_id:
        delete_message(CHATWOOT_BASE_URL, account_id, conversation_id, interim_id, admin_headers)

    # --- Send final reply ---
    send_message(CHATWOOT_BASE_URL, account_id, conversation_id, reply, bot_headers)

    # --- Handoff: open conversation and assign agent ---
    if is_handoff:
        logger.info("Handoff triggered — opening conversation and assigning agent.")
        toggle_status(CHATWOOT_BASE_URL, account_id, conversation_id, "open", bot_headers)
        assign_agent(CHATWOOT_BASE_URL, account_id, conversation_id, DEFAULT_ASSIGNEE_ID, admin_headers)

    return _http(200, {"status": "success"})


def _http(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
