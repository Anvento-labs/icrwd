import json
import base64
import os
import logging
import hashlib
import tempfile
import urllib.request
import urllib.error

from app.graphs.orchestrate_graph import app_graph
from app.graphs.receipt_graph import graph as receipt_graph
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

MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20MB
MIN_IMAGE_BYTES = 100  # small guardrail; matches devyansh-lambda


def _get_chatwoot_attachments(data):
    attachments = data.get("attachments") or []
    if attachments:
        return attachments if isinstance(attachments, list) else []
    messages = (data.get("conversation") or {}).get("messages") or []
    if messages:
        last = messages[-1] if isinstance(messages, list) else {}
        att = last.get("attachments") or []
        return att if isinstance(att, list) else []
    return []


def _fetch_image_bytes_from_data_url(data_url: str, chatwoot_image_host: str) -> bytes | None:
    """
    Fetch image bytes from Chatwoot attachment data_url.

    Supports:
    - URL form: http(s)://... (with 0.0.0.0 replaced by chatwoot_image_host)
    - inline data URL: data:image/...;base64,....
    """
    if not data_url or not str(data_url).strip():
        return None

    data_url = str(data_url).strip()

    # Inline base64
    if data_url.startswith("data:") and "base64," in data_url:
        try:
            b64 = data_url.split("base64,", 1)[1]
            return base64.b64decode(b64, validate=True)
        except Exception:
            return None

    # URL form
    fetch_url = data_url.replace("0.0.0.0", chatwoot_image_host)
    try:
        req = urllib.request.Request(fetch_url, headers={"User-Agent": "CRWD-Receipt-Validator/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        logger.warning("Chatwoot image fetch failed | url=%s | error=%s", fetch_url[:80], e)
        return None


def _write_image_to_tmp(image_bytes: bytes, conversation_id: int | str) -> tuple[str, str] | tuple[None, None]:
    """
    Validate image size, compute sha256, and write to /tmp.
    Returns (file_path, image_hash) or (None, None).
    """
    if not image_bytes:
        return None, None

    if not (MIN_IMAGE_BYTES <= len(image_bytes) <= MAX_IMAGE_BYTES):
        return None, None

    image_hash = hashlib.sha256(image_bytes).hexdigest()
    # Identify JPEG vs PNG by magic bytes (mirrors devyansh-lambda handler behavior)
    is_jpeg = len(image_bytes) >= 3 and image_bytes[:3] == b"\xff\xd8\xff"
    suffix = ".jpg" if is_jpeg else ".png"

    prefix = f"receipt_{str(conversation_id)[:32].replace('/', '_')}_"
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir="/tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(image_bytes)
        return path, image_hash
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        return None, None


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

    # Detect if this webhook contains an image attachment for receipt validation.
    # For receipt images, `content` may be empty, so only require content when no image exists.
    attachments = _get_chatwoot_attachments(payload)
    image_attachment = None
    for att in attachments:
        if not isinstance(att, dict):
            continue
        file_type = (att.get("file_type") or "").lower()
        if file_type == "image" or att.get("data_url"):
            image_attachment = att
            break

    has_image = bool(image_attachment and image_attachment.get("data_url"))

    if account_id is None or conversation_id is None or (not content and not has_image):
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

    # --- Invoke LangGraph (chat vs receipt) ---
    receipt_file_path = None
    is_handoff = False
    try:
        if has_image:
            logger.info("Invoking receipt graph (image validation)")

            chatwoot_image_host = os.environ.get("CHATWOOT_IMAGE_HOST", "44.215.200.55")
            data_url = image_attachment.get("data_url")
            image_bytes = _fetch_image_bytes_from_data_url(data_url, chatwoot_image_host)
            if not image_bytes:
                raise ValueError("Failed to fetch/parse image attachment bytes.")

            receipt_file_path, image_hash = _write_image_to_tmp(image_bytes, conversation_id)
            if not receipt_file_path or not image_hash:
                raise ValueError("Image size out of allowed range or write to /tmp failed.")

            sender = payload.get("sender") or {}
            user_id = None
            if sender.get("id") is not None:
                user_id = str(sender["id"])
            elif sender.get("email"):
                user_id = str(sender["email"])

            contact_inbox = payload.get("contact_inbox") or {}
            if not user_id and contact_inbox.get("contact_id") is not None:
                user_id = str(contact_inbox["contact_id"])

            custom = payload.get("custom_attributes") or (payload.get("conversation") or {}).get("custom_attributes") or {}
            campaign_id = custom.get("campaign_id")
            if campaign_id is not None:
                campaign_id = str(campaign_id)

            initial_state = {
                "receipt_file_path": receipt_file_path,
                "image_hash": image_hash,
                "user_id": user_id,
                "campaign_id": campaign_id,
                "conversation_id": str(conversation_id),
            }

            final_state = receipt_graph.invoke(initial_state)
            reply = final_state.get("reply_message") or "Receipt processing completed."
        else:
            logger.info(f"Invoking chat graph for: {content[:100]}")
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
    finally:
        # Cleanup /tmp receipt file
        try:
            if receipt_file_path and os.path.isfile(receipt_file_path):
                os.remove(receipt_file_path)
        except Exception:
            pass

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
