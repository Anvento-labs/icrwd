"""
Node 1: Input, S3 upload, duplicate check.
Delegates to steps.run_input_s3_duplicate.
"""

import logging
from typing import Any, Dict

from state import AIEngineState
from steps import run_input_s3_duplicate

logger = logging.getLogger(__name__)


def node_input_s3_duplicate(state: AIEngineState) -> Dict[str, Any]:
    """
    LangGraph node: receipt input validation, duplicate check, S3 upload.
    Returns full updated state for LangGraph to merge.
    """
    logger.info("Node called: input_s3_duplicate")
    out = run_input_s3_duplicate(state)
    logger.info(
        "Node input_s3_duplicate done | is_duplicate=%s | input_validation_status=%s",
        out.get("is_duplicate", False),
        out.get("input_validation_status"),
    )
    return out
