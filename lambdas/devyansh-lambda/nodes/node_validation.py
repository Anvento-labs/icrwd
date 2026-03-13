"""
Node 3: Data validation against campaign rules.
Multi-proof: if campaign requires more proof types, sets reply_message and pending_proof_types.
Otherwise delegates to steps.run_validation (which sets reply_message).
"""

import logging
from typing import Any, Dict

from state import AIEngineState
from steps.step3_validation import run_validation, _check_multiproof_pending

logger = logging.getLogger(__name__)


def node_validation(state: AIEngineState) -> Dict[str, Any]:
    """
    LangGraph node: validate extracted data against user campaigns (MongoDB).
    If campaign has required_proof_types and not all submitted: set reply_message and pending_proof_types.
    Else run full validation and set final_decision, reply_message, etc.
    """
    logger.info("[validation] Node called")
    multiproof = _check_multiproof_pending(state)
    if multiproof is not None:
        logger.info(
            "[validation] Multi-proof pending | pending_proof_types=%s | reply_message set",
            multiproof.get("pending_proof_types"),
        )
        return multiproof
    out = run_validation(state)
    logger.info(
        "[validation] Node done | final_decision=%s | validation_status=%s | score=%s | reply_message=%s",
        out.get("final_decision"),
        out.get("validation_status"),
        out.get("validation_score"),
        "set" if out.get("reply_message") else "none",
    )
    return out
