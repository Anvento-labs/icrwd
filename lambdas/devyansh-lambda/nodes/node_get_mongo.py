"""
Node: Get MongoDB data (read-only). Duplicate check, user, campaign rules, proof session.
Sets reply_message when duplicate so handler can send it.
"""

import logging
from typing import Any, Dict

from state import AIEngineState
from config import (
    MONGODB_URI,
    MONGODB_DATABASE,
    MONGODB_CRWDS_COLLECTION,
    MONGODB_USERS_COLLECTION,
    MONGODB_RECEIPT_HASH_DATABASE,
    MONGODB_RECEIPT_HASH_COLLECTION,
    MONGODB_PROOF_SESSIONS_DATABASE,
    MONGODB_PROOF_SESSIONS_COLLECTION,
    MONGODB_CAMPAIGN_RULES_COLLECTION,
)
from services.mongodb_campaigns import (
    receipt_hash_exists,
    get_user,
    get_campaign_rules,
    proof_session_get,
)

logger = logging.getLogger(__name__)

DUPLICATE_REPLY = "This image has already been submitted."


def node_get_mongo(state: AIEngineState) -> Dict[str, Any]:
    """
    LangGraph node: read-only. Duplicate check, load user, campaign_rules, proof_session.
    When duplicate detected, sets reply_message so handler can send it.
    """
    logger.info("[get_mongo] Node called | user_id=%s | campaign_id=%s", state.get("user_id"), state.get("campaign_id"))
    out: Dict[str, Any] = {}

    if not MONGODB_URI:
        logger.info("[get_mongo] MONGODB_URI not set; skipping reads")
        return out

    user_id = state.get("user_id") or ""
    campaign_id = state.get("campaign_id") or ""
    image_hash = state.get("image_hash") or ""
    conversation_id = state.get("conversation_id")

    # Duplicate check
    if image_hash:
        is_dup = receipt_hash_exists(
            MONGODB_URI,
            MONGODB_RECEIPT_HASH_DATABASE,
            MONGODB_RECEIPT_HASH_COLLECTION,
            image_hash,
        )
        if is_dup:
            logger.info("[get_mongo] Duplicate detected | image_hash_prefix=%s", image_hash[:16] if len(image_hash) > 16 else image_hash)
            out["is_duplicate"] = True
            out["reply_message"] = DUPLICATE_REPLY
            return out
    out["is_duplicate"] = False

    # User
    if user_id:
        user = get_user(user_id, MONGODB_URI, MONGODB_DATABASE, MONGODB_USERS_COLLECTION)
        out["user"] = user

    # Campaign rules (with required_proof_types)
    if campaign_id:
        rules = get_campaign_rules(
            campaign_id,
            MONGODB_URI,
            MONGODB_DATABASE,
            MONGODB_CRWDS_COLLECTION,
            MONGODB_CAMPAIGN_RULES_COLLECTION,
        )
        if rules:
            out["campaign_rules"] = rules
            out["required_proof_types"] = rules.get("required_proof_types") or []

    # Proof session (for multi-proof continue flow)
    if user_id and campaign_id:
        session = proof_session_get(
            MONGODB_URI,
            MONGODB_PROOF_SESSIONS_DATABASE,
            MONGODB_PROOF_SESSIONS_COLLECTION,
            user_id,
            campaign_id,
            conversation_id,
        )
        if session:
            out["proof_session_id"] = session.get("session_id")
            out["submitted_proofs"] = session.get("submitted_proofs") or []
            if not out.get("required_proof_types") and session.get("required_proof_types"):
                out["required_proof_types"] = session["required_proof_types"]
            logger.info("[get_mongo] proof_session loaded | submitted_count=%s", len(out["submitted_proofs"]))

    logger.info(
        "[get_mongo] Node done | is_duplicate=%s | has_user=%s | has_rules=%s | required_proof_types=%s",
        out.get("is_duplicate"),
        "user" in out,
        "campaign_rules" in out,
        out.get("required_proof_types", []),
    )
    return out
