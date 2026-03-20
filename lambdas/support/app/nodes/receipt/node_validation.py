"""
Receipt node: validation against campaign rules + multiproof handling.
"""

import logging
from typing import Any, Dict

from app.tools.receipt_validation_tool import run_validation, _check_multiproof_pending

logger = logging.getLogger(__name__)


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node:
    - If multiproof is pending, return update containing reply_message + pending_proof_types.
    - Otherwise run full validation and return the full validation result.
    """
    logger.info("[receipt:validation] Node called")

    multiproof = _check_multiproof_pending(state)
    if multiproof is not None:
        logger.info(
            "[receipt:validation] Multi-proof pending | pending_proof_types=%s | reply_message set",
            multiproof.get("pending_proof_types"),
        )
        return multiproof

    out = run_validation(state)
    logger.info(
        "[receipt:validation] Node done | final_decision=%s | validation_status=%s | score=%s",
        out.get("final_decision"),
        out.get("validation_status"),
        out.get("validation_score"),
    )
    # Ensure reply_message exists for handler reply
    if not out.get("reply_message"):
        review_reason = out.get("review_reason") or ""
        if out.get("requires_manual_review"):
            out["reply_message"] = review_reason or "Receipt is under review."
        elif review_reason:
            out["reply_message"] = review_reason
        else:
            out["reply_message"] = "Receipt processing completed."
    return out

