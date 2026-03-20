"""
Receipt node: duplicate check + Mongo reads (user, rules, proof session).
"""

import logging
from typing import Any, Dict

from app.receipt_config import (
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
from app.tools.receipt_mongo_tool import (
    receipt_hash_exists,
    get_user,
    get_campaign_rules,
    proof_session_get,
)

logger = logging.getLogger(__name__)

DUPLICATE_REPLY = "This image has already been submitted."


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: read-only.

    Updates:
    - is_duplicate: bool
    - reply_message: set when duplicate detected
    - required_proof_types: from campaign rules (campaign_id)
    - submitted_proofs + proof_session_id: from proof_session_get
    """
    logger.info(
        "[receipt:get_mongo] Node called | user_id=%s | campaign_id=%s",
        state.get("user_id"),
        state.get("campaign_id"),
    )

    out: Dict[str, Any] = {"is_duplicate": False}

    if not MONGODB_URI:
        logger.info("[receipt:get_mongo] MONGODB_URI not set; skipping duplicate/rules/session reads")
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
            logger.info("[receipt:get_mongo] Duplicate detected | image_hash_prefix=%s", image_hash[:16])
            out["is_duplicate"] = True
            out["reply_message"] = DUPLICATE_REPLY
            return out

    # User
    if user_id:
        out["user"] = get_user(user_id, MONGODB_URI, MONGODB_DATABASE, MONGODB_USERS_COLLECTION)

    # Campaign rules (drives required_proof_types for multiproof)
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

    # Proof session (multi-proof continue flow)
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
            logger.info(
                "[receipt:get_mongo] proof_session loaded | submitted_count=%s",
                len(out.get("submitted_proofs") or []),
            )

    # Ensure keys exist for downstream nodes
    out.setdefault("required_proof_types", [])
    out.setdefault("submitted_proofs", [])
    out.setdefault("pending_proof_types", [])

    return out

