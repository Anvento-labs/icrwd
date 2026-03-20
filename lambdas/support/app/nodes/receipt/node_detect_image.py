"""
Receipt node: classify image type + run fraud/validity check + extraction.
"""

import logging
from typing import Any, Dict

from app.receipt_config import BEDROCK_MODEL_ID, BEDROCK_REGION, FRAUD_CHECK_CONFIDENCE_THRESHOLD
from app.tools.receipt_bedrock_tool import detect_image_type_fraud_extract

logger = logging.getLogger(__name__)

DETECT_INVALID_REPLY = "This image could not be accepted: it did not pass our validity check."


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: classify image type, validate (fraud check), and extract data.

    Returns a partial state update (dict) including:
    - detected_image_type
    - is_valid_image
    - validity_confidence
    - detection_rejection_reason
    - extracted_data
    - flattened fields for validation: merchant_name, purchase_date, order_number, total_amount, line_items, extraction_confidence
    - reply_message when image is invalid
    """
    receipt_file_path = state.get("receipt_file_path")
    if not receipt_file_path:
        logger.warning("[receipt:detect_image] No receipt_file_path in state")
        return {
            "detected_image_type": None,
            "is_valid_image": False,
            "validity_confidence": 0.0,
            "detection_rejection_reason": "No image path in state",
            "extracted_data": None,
            "reply_message": DETECT_INVALID_REPLY,
        }

    result, _rejection_reason = detect_image_type_fraud_extract(
        image_path=receipt_file_path,
        model_id=BEDROCK_MODEL_ID,
        region=BEDROCK_REGION,
        validity_confidence_threshold=FRAUD_CHECK_CONFIDENCE_THRESHOLD,
    )

    out: Dict[str, Any] = {
        "detected_image_type": result.get("detected_image_type"),
        "is_valid_image": result.get("is_valid_image", False),
        "validity_confidence": result.get("validity_confidence"),
        "detection_rejection_reason": result.get("detection_rejection_reason"),
        "extracted_data": result.get("extracted_data"),
    }

    extraction = out.get("extracted_data")
    if extraction and isinstance(extraction, dict):
        out["merchant_name"] = extraction.get("merchant_name")
        out["purchase_date"] = extraction.get("purchase_date") or extraction.get("order_date")
        out["order_number"] = extraction.get("order_number") or extraction.get("order_id")
        out["total_amount"] = extraction.get("total_amount")
        out["extraction_confidence"] = extraction.get("extraction_confidence")
        out["line_items"] = extraction.get("line_items") or []
    else:
        out["merchant_name"] = None
        out["purchase_date"] = None
        out["order_number"] = None
        out["total_amount"] = None
        out["extraction_confidence"] = None
        out["line_items"] = []

    if not out.get("is_valid_image"):
        out["reply_message"] = DETECT_INVALID_REPLY
        if out.get("detection_rejection_reason"):
            out["reply_message"] = out["detection_rejection_reason"]

    logger.info(
        "[receipt:detect_image] Node done | type=%s | is_valid=%s | has_extraction=%s",
        out.get("detected_image_type"),
        out.get("is_valid_image"),
        bool(out.get("extracted_data")),
    )
    return out

