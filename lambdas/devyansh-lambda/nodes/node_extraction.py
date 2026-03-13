"""
Node 2: Data extraction from receipt image.
Delegates to steps.run_extraction.
"""

import logging
from typing import Any, Dict

from state import AIEngineState
from steps import run_extraction

logger = logging.getLogger(__name__)


def node_extraction(state: AIEngineState) -> Dict[str, Any]:
    """
    LangGraph node: extract structured data (Document AI + Bedrock fallback).
    Returns full updated state for LangGraph to merge.
    """
    logger.info("Node called: extraction")
    out = run_extraction(state)
    logger.info(
        "Node extraction done | merchant=%s | confidence=%s | errors=%s",
        out.get("merchant_name"),
        out.get("extraction_confidence"),
        len(out.get("extraction_errors", [])),
    )
    return out
