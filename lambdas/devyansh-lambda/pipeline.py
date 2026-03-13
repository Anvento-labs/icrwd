"""
Receipt verification pipeline via LangGraph.
Runs workflow: input_s3_duplicate -> (conditional) -> extraction -> validation -> END.
"""

import logging

from state import AIEngineState
from workflow import get_compiled_graph

logger = logging.getLogger(__name__)


def run_receipt_verification(initial_state: AIEngineState) -> AIEngineState:
    """
    Run the full receipt verification pipeline using the LangGraph workflow.

    Nodes:
    1. input_s3_duplicate: Input validation, duplicate check, S3 upload.
    2. extraction: Document AI + Bedrock fallback (skipped if duplicate/invalid).
    3. validation: Validate against user campaigns (MongoDB).

    Args:
        initial_state: State dict with receipt_image_base64, user_id, campaign_id (optional),
                       and empty lists for errors/audit_trail.

    Returns:
        Final state dict with validation_status, final_decision, receipt_s3_key, etc.
    """
    logger.info("Pipeline started | workflow=LangGraph(input_s3_duplicate->extraction->validation)")
    graph = get_compiled_graph()
    result = graph.invoke(initial_state)
    # LangGraph may return state in a wrapper; normalize to dict
    out = result if hasattr(result, "get") else dict(result)
    logger.info(
        "Pipeline finished | final_decision=%s | validation_status=%s | is_duplicate=%s",
        out.get("final_decision"),
        out.get("validation_status"),
        out.get("is_duplicate", False),
    )
    logger.info(
        "Pipeline state summary | receipt_s3_bucket=%s | receipt_s3_key=%s | input_validation_status=%s | extraction_confidence=%s | errors_count=%s",
        out.get("receipt_s3_bucket"),
        out.get("receipt_s3_key"),
        out.get("input_validation_status"),
        out.get("extraction_confidence"),
        len(out.get("input_validation_errors", [])) + len(out.get("extraction_errors", [])),
    )
    return out
