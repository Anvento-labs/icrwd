"""
Step: Detect image type + fraud check + extraction (single VLM call).
Used by the detect_image node in the 4-node pipeline.
"""

import logging
from typing import Any, Dict

from state import AIEngineState
from config import BEDROCK_MODEL_ID, BEDROCK_REGION, FRAUD_CHECK_CONFIDENCE_THRESHOLD
from services.bedrock_vlm import detect_image_type_fraud_extract

logger = logging.getLogger(__name__)

# Reply when image fails validity (set by detect node for handler to send)
DETECT_INVALID_REPLY = "This image could not be accepted: it did not pass our validity check."


def run_detect_image(state: AIEngineState) -> Dict[str, Any]:
    """
    Run VLM: classify image type (order_receipt, order_id, review, selfie),
    validity check, and type-specific extraction.
    Returns state update with detected_image_type, is_valid_image, validity_confidence,
    extracted_data (and flattened merchant_name, purchase_date, etc. when present), reply_message if invalid.
    """
    logger.info("[detect_image] Step started | receipt_file_path=%s", state.get("receipt_file_path"))
    receipt_file_path = state.get("receipt_file_path")
    if not receipt_file_path:
        logger.warning("[detect_image] No receipt_file_path in state")
        return {
            "detected_image_type": None,
            "is_valid_image": False,
            "validity_confidence": 0.0,
            "detection_rejection_reason": "No image path in state",
            "reply_message": DETECT_INVALID_REPLY,
        }

    result, rejection_reason = detect_image_type_fraud_extract(
        image_path=receipt_file_path,
        model_id=BEDROCK_MODEL_ID,
        region=BEDROCK_REGION,
        validity_confidence_threshold=FRAUD_CHECK_CONFIDENCE_THRESHOLD,
    )

    out = {
        "detected_image_type": result.get("detected_image_type"),
        "is_valid_image": result.get("is_valid_image", False),
        "validity_confidence": result.get("validity_confidence"),
        "detection_rejection_reason": result.get("detection_rejection_reason"),
        "extracted_data": result.get("extracted_data"),
    }

    # Flatten common extraction fields for validation (order_receipt / order_id)
    extraction = result.get("extracted_data")
    if extraction and isinstance(extraction, dict):
        out["merchant_name"] = extraction.get("merchant_name")
        out["purchase_date"] = extraction.get("purchase_date") or extraction.get("order_date")
        out["order_number"] = extraction.get("order_number") or extraction.get("order_id")
        out["total_amount"] = extraction.get("total_amount")
        out["extraction_confidence"] = extraction.get("extraction_confidence")
        if extraction.get("line_items"):
            out["line_items"] = extraction["line_items"]
        else:
            out["line_items"] = []

    if not result.get("is_valid_image"):
        out["reply_message"] = DETECT_INVALID_REPLY
        if result.get("detection_rejection_reason"):
            out["reply_message"] = result["detection_rejection_reason"]

    logger.info(
        "[detect_image] Step done | type=%s | is_valid=%s | has_extraction=%s",
        out.get("detected_image_type"),
        out.get("is_valid_image"),
        bool(out.get("extracted_data")),
    )
    return out
