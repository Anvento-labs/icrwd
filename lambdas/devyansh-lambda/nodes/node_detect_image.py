"""
Node: Detect image type + fraud check + extraction (single VLM call).
Delegates to steps.run_detect_image. Sets reply_message when image is invalid.
"""

import logging
from typing import Any, Dict

from state import AIEngineState
from steps.step_detect_image import run_detect_image

logger = logging.getLogger(__name__)


def node_detect_image(state: AIEngineState) -> Dict[str, Any]:
    """
    LangGraph node: classify image type, validate (fraud check), extract data.
    Returns state update. Sets reply_message when image fails validity so handler can send it.
    """
    logger.info("[detect_image] Node called")
    out = run_detect_image(state)
    logger.info(
        "[detect_image] Node done | type=%s | is_valid=%s | reply_message=%s",
        out.get("detected_image_type"),
        out.get("is_valid_image"),
        "set" if out.get("reply_message") else "none",
    )
    return out
