"""
Lambda entrypoint for AI engine.
Invoked by Chatwoot webhook only. Parses webhook body, fetches image from attachments,
runs proof pipeline, sends reply to the conversation.
"""

import base64
import hashlib
import json
import logging
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Tuple

# Max image size 20MB
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MIN_IMAGE_BYTES = 100

# Configure root logger first so INFO from all modules (steps, services) reaches CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s]\t%(name)s\t%(message)s",
    force=True,
)

from state import AIEngineState
from services.mongodb_campaigns import proof_session_get
from workflow import get_compiled_graph_proof
from config import (
    BYPASS_VALIDATION,
    CHATWOOT_IMAGE_HOST,
    CHATWOOT_BASE_URL,
    CHATWOOT_BOT_TOKEN,
    CHATWOOT_USER_TOKEN,
    MONGODB_URI,
    MONGODB_PROOF_SESSIONS_DATABASE,
    MONGODB_PROOF_SESSIONS_COLLECTION,
)

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


def _get_chatwoot_attachments(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of attachment dicts from Chatwoot payload (top-level or from last message)."""
    attachments = data.get("attachments") or []
    if attachments:
        return attachments if isinstance(attachments, list) else []
    messages = (data.get("conversation") or {}).get("messages") or []
    if messages:
        last = messages[-1] if isinstance(messages, list) else {}
        att = last.get("attachments") or []
        return att if isinstance(att, list) else []
    return []


def _fetch_image_from_url(url: str, chatwoot_host: str, timeout_sec: int = 30) -> bytes | None:
    """Fetch image bytes from URL; replace 0.0.0.0 in URL with chatwoot_host so Lambda can reach it."""
    if not url or not url.strip():
        return None
    fetch_url = url.replace("0.0.0.0", chatwoot_host).strip()
    try:
        req = urllib.request.Request(fetch_url, headers={"User-Agent": "CRWD-Receipt-Validator/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return resp.read()
    except Exception as e:
        logger.warning("Chatwoot image fetch failed | url=%s | error=%s", fetch_url[:80], e)
        return None


def _get_image_and_context_from_chatwoot(data: Dict[str, Any]) -> Tuple[str | None, str | None, str | None, Dict[str, Any] | None]:
    """
    Extract receipt image (base64), user_id, and Chatwoot reply context from webhook payload.
    Returns (image_b64, user_id, campaign_id, chatwoot_reply_context).
    chatwoot_reply_context = {account_id, conversation_id} for sending reply to the conversation.
    """
    account = data.get("account") or {}
    conversation = data.get("conversation") or {}
    account_id = account.get("id")
    conversation_id = conversation.get("id")
    chatwoot_reply_context = None
    if account_id is not None and conversation_id is not None:
        chatwoot_reply_context = {"account_id": account_id, "conversation_id": conversation_id}

    attachments = _get_chatwoot_attachments(data)
    image_attachment = None
    for att in attachments:
        if not isinstance(att, dict):
            continue
        ft = (att.get("file_type") or "").lower()
        if ft == "image" or att.get("data_url"):
            image_attachment = att
            break
    if not image_attachment:
        logger.info("Chatwoot payload: no image attachment found")
        return None, None, None, chatwoot_reply_context
    data_url = image_attachment.get("data_url")
    if not data_url:
        logger.info("Chatwoot payload: image attachment has no data_url")
        return None, None, None, chatwoot_reply_context
    image_bytes = _fetch_image_from_url(data_url, CHATWOOT_IMAGE_HOST)
    if not image_bytes:
        return None, None, None, chatwoot_reply_context
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    logger.info("Chatwoot payload: fetched image from data_url | size_bytes=%s", len(image_bytes))
    sender = data.get("sender") or {}
    user_id = None
    if sender.get("id") is not None:
        user_id = str(sender["id"])
    elif sender.get("email"):
        user_id = str(sender["email"])
    contact_inbox = data.get("contact_inbox") or {}
    if not user_id and contact_inbox.get("contact_id") is not None:
        user_id = str(contact_inbox["contact_id"])
    custom = data.get("custom_attributes") or (data.get("conversation") or {}).get("custom_attributes") or {}
    campaign_id = custom.get("campaign_id")
    if campaign_id is not None:
        campaign_id = str(campaign_id)
    return image_b64, user_id, campaign_id, chatwoot_reply_context


def _format_chatwoot_reply_message(final_state: Dict[str, Any]) -> str:
    """Format pipeline result as a short message for the Chatwoot user."""
    final_decision = final_state.get("final_decision")
    validation_status = final_state.get("validation_status")
    review_reason = final_state.get("review_reason")
    is_duplicate = final_state.get("is_duplicate", False)
    campaign_name = final_state.get("campaign_name")
    validation_score = final_state.get("validation_score")
    requires_manual_review = final_state.get("requires_manual_review", False)

    if is_duplicate:
        return review_reason or "Duplicate receipt: this image has already been submitted."
    if review_reason and (final_decision == "REJECTED" or validation_status == "rejected"):
        return review_reason
    if final_decision == "APPROVED":
        parts = ["Receipt approved."]
        if campaign_name:
            parts.append(f"Campaign: {campaign_name}.")
        if validation_score is not None:
            parts.append(f"Score: {validation_score:.0%}.")
        return " ".join(parts)
    if requires_manual_review or final_decision == "PENDING_REVIEW":
        parts = ["Receipt is under review."]
        if review_reason:
            parts.append(review_reason)
        if campaign_name:
            parts.append(f"Campaign: {campaign_name}.")
        return " ".join(parts)
    if review_reason:
        return review_reason
    if validation_status:
        return f"Result: {validation_status}."
    return "Receipt processing completed."


def _chatwoot_send_message(account_id: Any, conversation_id: Any, content: str) -> bool:
    """
    Send an outgoing message to the Chatwoot conversation (same pattern as shresth_lambda_function).
    POST to {base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages
    """
    if not CHATWOOT_BASE_URL or not CHATWOOT_BOT_TOKEN:
        logger.warning("Chatwoot reply skipped: CHATWOOT_BASE_URL or CHATWOOT_BOT_TOKEN not set")
        return False
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
    headers = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_BOT_TOKEN,
    }
    data = {"content": content, "message_type": "outgoing"}
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    logger.info(
        "Calling Chatwoot message API | account_id=%s | conversation_id=%s | url=%s",
        account_id,
        conversation_id,
        url,
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        logger.info("Chatwoot reply sent | account_id=%s | conversation_id=%s", account_id, conversation_id)
        return True
    except urllib.error.HTTPError as e:
        logger.error("Chatwoot API error %s: %s", e.code, e.read())
        return False
    except urllib.error.URLError as e:
        logger.error("Chatwoot URLError: %s", e.reason)
        return False


def _chatwoot_toggle_typing(account_id: Any, conversation_id: Any, typing_on: bool) -> bool:
    """
    Turn Chatwoot typing indicator on or off for the conversation (no message sent).
    Uses CHATWOOT_USER_TOKEN (typing endpoint is not authorized for bots).
    POST to {base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_typing_status
    """
    if not CHATWOOT_BASE_URL or not CHATWOOT_USER_TOKEN:
        return False
    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_typing_status"
    headers = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_USER_TOKEN,
    }
    data = {"typing_status": "on" if typing_on else "off"}
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        logger.info("Chatwoot typing %s | account_id=%s | conversation_id=%s", "on" if typing_on else "off", account_id, conversation_id)
        return True
    except urllib.error.HTTPError as e:
        logger.warning("Chatwoot typing API error %s: %s", e.code, e.read())
        return False
    except urllib.error.URLError as e:
        logger.warning("Chatwoot typing URLError: %s", e.reason)
        return False


def _parse_chatwoot_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Lambda event as Chatwoot webhook body (JSON). Returns parsed dict or empty dict on failure."""
    body = event.get("body")
    if body is None:
        return {}
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    return {}


def _decode_image_and_prepare_file(
    image_b64: str,
    request_id: str | None,
) -> Tuple[str | None, str | None]:
    """
    Decode base64 image, validate size, compute SHA-256 hash, write to /tmp.
    Returns (receipt_file_path, image_hash). Returns (None, None) on failure.
    """
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception as e:
        logger.warning("Image base64 decode failed | request_id=%s | error=%s", request_id, e)
        return None, None
    if not (MIN_IMAGE_BYTES <= len(raw) <= MAX_IMAGE_BYTES):
        logger.warning(
            "Image size out of range | request_id=%s | len=%s",
            request_id,
            len(raw),
        )
        return None, None
    image_hash = hashlib.sha256(raw).hexdigest()
    prefix = (request_id or "receipt")[:32].replace("/", "_")
    suffix = ".jpg" if raw[:3] == b"\xff\xd8\xff" else ".png"
    fd, path = tempfile.mkstemp(prefix=f"receipt_{prefix}_", suffix=suffix, dir="/tmp")
    try:
        os.write(fd, raw)
        os.close(fd)
        fd = None
        return path, image_hash
    except Exception as e:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        logger.warning("Write /tmp receipt failed | request_id=%s | error=%s", request_id, e)
        return None, None


def _build_initial_state_proof(
    receipt_file_path: str | None,
    image_hash: str | None,
    user_id: str | None,
    campaign_id: str | None,
    conversation_id: str | None,
    session_doc: Dict[str, Any] | None,
) -> AIEngineState:
    """Build initial state for the proof pipeline (4-node graph)."""
    state: AIEngineState = {
        "receipt_file_path": receipt_file_path,
        "image_hash": image_hash or "",
        "user_id": user_id,
        "campaign_id": campaign_id,
        "conversation_id": conversation_id,
        "submission_timestamp": datetime.utcnow().isoformat() + "Z",
        "input_validation_errors": [],
        "extraction_errors": [],
        "violation_details": [],
        "requires_manual_review": False,
        "audit_trail": [],
        "bypass_validation": BYPASS_VALIDATION,
    }
    if session_doc:
        state["proof_session_id"] = session_doc.get("session_id")
        state["submitted_proofs"] = list(session_doc.get("submitted_proofs") or [])
        req = session_doc.get("required_proof_types")
        if req is not None:
            state["required_proof_types"] = list(req)
    return state


def _build_response(final_state: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """Build API Gateway response (slim body + optional full state in debug)."""
    body = {
        "final_decision": final_state.get("final_decision"),
        "validation_status": final_state.get("validation_status"),
        "is_duplicate": final_state.get("is_duplicate", False),
        "receipt_s3_key": final_state.get("receipt_s3_key"),
        "receipt_s3_bucket": final_state.get("receipt_s3_bucket"),
        "validation_score": final_state.get("validation_score"),
        "extraction_confidence": final_state.get("extraction_confidence"),
        "requires_manual_review": final_state.get("requires_manual_review", False),
        "review_reason": final_state.get("review_reason"),
        "campaign_id": final_state.get("campaign_id"),
        "campaign_name": final_state.get("campaign_name"),
    }
    if os.environ.get("DEBUG_RESPONSE"):
        body["state"] = {
            k: v for k, v in final_state.items()
            if k not in ("receipt_image_base64",)  # avoid huge payload
        }
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for AI engine. Invoked by Chatwoot webhook only.
    Parses webhook body, fetches image from attachments, runs proof pipeline, sends reply to the conversation.
    """
    request_id = getattr(context, "aws_request_id", None) if context else None
    logger.info("LAMBDA TRIGGERED | request_id=%s | source=CHATWOOT", request_id)

    data = _parse_chatwoot_event(event)
    if not data or not isinstance(data, dict):
        logger.warning("Invalid or missing Chatwoot body | request_id=%s", request_id)
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Bad request", "message": "Invalid Chatwoot webhook body."}),
        }

    try:
        image_b64, user_id, campaign_id, chatwoot_reply_context = _get_image_and_context_from_chatwoot(data)
    except Exception as e:
        logger.exception("Failed to parse Chatwoot payload: %s", e)
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Bad request", "message": str(e)}),
        }

    if not chatwoot_reply_context:
        logger.warning("Chatwoot payload missing account_id or conversation_id | request_id=%s", request_id)
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Bad request", "message": "Chatwoot payload must include account and conversation."}),
        }

    logger.info(
        "Chatwoot parsed | request_id=%s | has_image=%s | user_id=%s | campaign_id=%s",
        request_id,
        bool(image_b64),
        user_id,
        campaign_id,
    )

    if not image_b64:
        logger.warning("No image attachment in Chatwoot message | request_id=%s", request_id)
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Bad request",
                "message": "No image attachment in message. Please upload a receipt image.",
            }),
        }

    receipt_file_path, image_hash = _decode_image_and_prepare_file(image_b64, request_id)
    if not receipt_file_path or not image_hash:
        logger.warning("Image decode/hash/write failed | request_id=%s", request_id)
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Bad request",
                "message": "Invalid image or size: ensure base64 image is between 100 bytes and 20MB.",
            }),
        }

    conversation_id = None
    if chatwoot_reply_context:
        conversation_id = str(chatwoot_reply_context.get("conversation_id") or "")

    session_loaded = False
    session_doc = None
    if MONGODB_URI and user_id and campaign_id:
        try:
            session_doc = proof_session_get(
                MONGODB_URI,
                MONGODB_PROOF_SESSIONS_DATABASE,
                MONGODB_PROOF_SESSIONS_COLLECTION,
                user_id,
                campaign_id,
                conversation_id or None,
            )
            session_loaded = session_doc is not None
        except Exception as e:
            logger.warning("proof_session_get failed (non-fatal) | request_id=%s | error=%s", request_id, e)

    initial_state = _build_initial_state_proof(
        receipt_file_path,
        image_hash,
        user_id,
        campaign_id,
        conversation_id,
        session_doc,
    )

    logger.info(
        "Running proof pipeline | request_id=%s | user_id=%s | campaign_id=%s | session_loaded=%s",
        request_id,
        user_id,
        campaign_id,
        session_loaded,
    )

    _chatwoot_toggle_typing(
        chatwoot_reply_context["account_id"],
        chatwoot_reply_context["conversation_id"],
        True,
    )
    try:
        try:
            graph = get_compiled_graph_proof()
            final_state = graph.invoke(initial_state)
            final_state = final_state if isinstance(final_state, dict) else dict(final_state)
        except Exception as e:
            logger.exception("Proof pipeline failed | request_id=%s | error=%s", request_id, e)
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Internal server error",
                    "message": str(e),
                    "request_id": request_id,
                }, default=str),
            }
        logger.info(
            "Proof pipeline completed | request_id=%s | final_decision=%s | validation_status=%s | is_duplicate=%s | campaign_id=%s | reply_message=%s",
            request_id,
            final_state.get("final_decision"),
            final_state.get("validation_status"),
            final_state.get("is_duplicate", False),
            final_state.get("campaign_id"),
            "set" if final_state.get("reply_message") else "none",
        )
        reply_message = final_state.get("reply_message")
        if not reply_message:
            reply_message = _format_chatwoot_reply_message(final_state)
        _chatwoot_send_message(
            chatwoot_reply_context["account_id"],
            chatwoot_reply_context["conversation_id"],
            reply_message,
        )
        response = _build_response(final_state)
        if final_state.get("reply_message"):
            try:
                body_dict = json.loads(response.get("body", "{}"))
            except Exception:
                body_dict = {}
            body_dict["reply_message"] = final_state.get("reply_message")
            response["body"] = json.dumps(body_dict, default=str)
        logger.info("Response built | request_id=%s | status_code=%s", request_id, response.get("statusCode", 200))
        return response
    finally:
        _chatwoot_toggle_typing(
            chatwoot_reply_context["account_id"],
            chatwoot_reply_context["conversation_id"],
            False,
        )
        try:
            if receipt_file_path and os.path.isfile(receipt_file_path):
                os.remove(receipt_file_path)
        except Exception as e:
            logger.debug("Cleanup /tmp receipt file failed | path=%s | error=%s", receipt_file_path, e)
