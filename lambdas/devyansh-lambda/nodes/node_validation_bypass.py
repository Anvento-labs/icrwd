"""
Node: Validation bypass (when BYPASS_VALIDATION=true).
Sets final_decision=PENDING_REVIEW, validation_status=pending_review without calling MongoDB.
"""

import logging
from typing import Any, Dict

from state import AIEngineState
from steps import run_validation_bypass

logger = logging.getLogger(__name__)


def node_validation_bypass(state: AIEngineState) -> Dict[str, Any]:
    """
    LangGraph node: skip validation and set decision from bypass.
    Returns full updated state for LangGraph to merge.
    """
    logger.info("Node called: validation_bypass (BYPASS_VALIDATION=true)")
    out = run_validation_bypass(state)
    logger.info(
        "Node validation_bypass done | final_decision=%s | validation_status=%s",
        out.get("final_decision"),
        out.get("validation_status"),
    )
    return out
