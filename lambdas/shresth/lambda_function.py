import json
import os
import requests
import logging
from app.graph import app_graph 

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHATWOOT_BASE_URL = "http://44.215.200.55:3000".rstrip("/")
CHATWOOT_BOT_TOKEN = "LrqLxPvY4HEAn2BCYwyFYNcM" 

def lambda_handler(event, context):
    logger.info("Webhook received.")

    try:
        if 'body' in event and event['body']:
            payload = json.loads(event['body'])
        else:
            payload = event 
    except Exception as e:
        logger.error(f"Failed to parse event body: {e}")
        return {"statusCode": 400, "body": "Invalid JSON payload"}

    # 3. CRITICAL: Prevent Infinite Loops
    # Ignore any message that the bot or a human agent sends. Only process user messages.
    if payload.get("message_type") != "incoming":
        logger.info("Ignored non-incoming message.")
        return {"statusCode": 200, "body": json.dumps({"status": "ignored"})}

    # 4. EXTRACT CHATWOOT DATA
    user_message = payload.get("content")
    conversation_id = payload.get("conversation", {}).get("id")
    account_id = payload.get("account", {}).get("id")

    if not user_message or not conversation_id:
        logger.warning("Missing message content or conversation ID.")
        return {"statusCode": 200, "body": json.dumps({"status": "missing data"})}

    try:
        logger.info(f"Invoking LangGraph with question: {user_message}")
        final_state = app_graph.invoke({"question": user_message})
        bot_response = final_state.get("generation", "I am having trouble processing that.")
    except Exception as e:
        logger.error(f"LangGraph execution error: {e}")
        bot_response = "Sorry, my systems are experiencing a temporary error."

    # 6. ROUTER CHECK: Did the bot trigger a human handoff?
    is_handoff = "transferring" in bot_response.lower()

    # 7. SEND THE REPLY BACK TO CHATWOOT
    send_message_to_chatwoot(account_id, conversation_id, bot_response)

    # 8. IF HANDOFF, ALERT THE HUMAN AGENTS
    if is_handoff:
        logger.info("Handoff triggered. Opening conversation for human agents.")
        handoff_in_chatwoot(account_id, conversation_id)

    # Return HTTP 200 to acknowledge receipt of the webhook
    return {
        "statusCode": 200,
        "body": json.dumps({"status": "success"})
    }

def send_message_to_chatwoot(account_id, conversation_id, message_text):
    """Hits the Chatwoot API to post the AI's message into the chat widget."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
    headers = {
        "api_access_token": CHATWOOT_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "content": message_text,
        "message_type": "outgoing" 
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        logger.error(f"Failed to send message to Chatwoot: {response.text}")

def handoff_in_chatwoot(account_id, conversation_id):
    """Changes the Chatwoot conversation status to 'open' so humans see it in their inbox."""
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_status"
    headers = {
        "api_access_token": CHATWOOT_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    data = {"status": "open"}
    requests.post(url, headers=headers, json=data)