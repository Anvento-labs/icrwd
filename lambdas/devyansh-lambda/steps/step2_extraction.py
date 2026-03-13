"""
Step 2: Data extraction from receipt image.
Google Document AI first; if confidence >= threshold use it, else AWS Bedrock VLM.
Then normalize and apply vendor-specific parsing.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from state import AIEngineState
from config import (
    GOOGLE_CLOUD_PROJECT,
    DOCUMENT_AI_LOCATION,
    DOCUMENT_AI_PROCESSOR_ID,
    DOCUMENT_AI_CONFIDENCE_THRESHOLD,
    FRAUD_CHECK_CONFIDENCE_THRESHOLD,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
)
from services.document_ai import extract_receipt as docai_extract, is_available as docai_available
from services.bedrock_vlm import extract_receipt_with_fraud_check as bedrock_fraud_and_extract
from services.extraction_schema import (
    ExtractionResult,
    normalize_phone_number,
    detect_vendor_type,
    format_products_list,
    apply_vendor_specific_parsing,
)

logger = logging.getLogger(__name__)


def _docai_result_to_extraction_result(doc: Dict[str, Any], confidence: float) -> ExtractionResult:
    """Build ExtractionResult from Document AI result dict."""
    return ExtractionResult(
        merchant_name=doc.get("merchant_name"),
        purchase_date=doc.get("purchase_date"),
        order_number=doc.get("order_number"),
        total_amount=doc.get("total_amount"),
        tax_amount=doc.get("tax_amount"),
        place=doc.get("place"),
        line_items=doc.get("line_items", []),
        phone_number=doc.get("phone_number"),
        customer_name=doc.get("customer_name"),
        address=doc.get("address"),
        extraction_confidence=confidence,
        raw_response={"provider": "document_ai", "confidence": confidence},
    )


def run_extraction(state: AIEngineState) -> AIEngineState:
    """
    Step 2: Extract structured data from receipt.

    - Call Google Document AI; if confidence >= threshold use result
    - Else call AWS Bedrock VLM
    - Normalize phone, detect vendor, format products, apply vendor parsing
    - Write extracted_data, merchant_name, purchase_date, etc. to state
    """
    logger.info(
        "[extraction] Step 2 started | receipt_file_path=%s | is_duplicate=%s",
        state.get("receipt_file_path"),
        state.get("is_duplicate"),
    )
    audit_trail = list(state.get("audit_trail", []))
    errors = list(state.get("extraction_errors", []))
    out: Dict[str, Any] = {
        **state,
        "extraction_errors": errors,
        "extraction_confidence": 0.0,
        "audit_trail": audit_trail,
    }

    if state.get("is_duplicate"):
        logger.info("[extraction] Skipping: is_duplicate=True")
        return out

    receipt_file_path = state.get("receipt_file_path")
    file_type = state.get("file_type", "image")
    if not receipt_file_path:
        logger.warning("[extraction] Skipping: no receipt_file_path (Step 1 did not produce local path)")
        errors.append("Receipt file path not found (Step 1 did not produce local path)")
        audit_trail.append({
            "step": "extraction",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "skipped",
            "reason": "no_receipt_path",
            "status": "error",
        })
        return out

    logger.info("[extraction] Proceeding with extraction | file_type=%s", file_type)
    result: ExtractionResult | None = None
    docai_used = False
    docai_skipped_reason = None
    docai_error = None
    try:
        logger.info(
            "[extraction] Checking Document AI | GOOGLE_CLOUD_PROJECT=%s | DOCUMENT_AI_PROCESSOR_ID=%s | DOCUMENT_AI_LOCATION=%s",
            GOOGLE_CLOUD_PROJECT or "(empty)",
            DOCUMENT_AI_PROCESSOR_ID or "(empty)",
            DOCUMENT_AI_LOCATION,
        )
        if not GOOGLE_CLOUD_PROJECT or not GOOGLE_CLOUD_PROJECT.strip():
            docai_skipped_reason = "missing or empty GOOGLE_CLOUD_PROJECT"
            logger.info("[extraction] Document AI: skipped | reason=%s", docai_skipped_reason)
        elif not DOCUMENT_AI_PROCESSOR_ID or not DOCUMENT_AI_PROCESSOR_ID.strip():
            docai_skipped_reason = "missing or empty DOCUMENT_AI_PROCESSOR_ID"
            logger.info("[extraction] Document AI: skipped | reason=%s", docai_skipped_reason)
        elif not docai_available(GOOGLE_CLOUD_PROJECT, DOCUMENT_AI_PROCESSOR_ID):
            docai_skipped_reason = "Document AI library not available or not configured (see [document_ai] logs)"
            logger.info("[extraction] Document AI: skipped | reason=%s", docai_skipped_reason)
        else:
            logger.info("[extraction] Document AI: calling API (project=%s, processor=%s)", GOOGLE_CLOUD_PROJECT, DOCUMENT_AI_PROCESSOR_ID)
            docai_result = docai_extract(
                receipt_file_path,
                project_id=GOOGLE_CLOUD_PROJECT,
                location=DOCUMENT_AI_LOCATION,
                processor_id=DOCUMENT_AI_PROCESSOR_ID,
            )
            confidence = docai_result.get("extraction_confidence", 0.0)
            logger.info(
                "[extraction] Document AI: returned | confidence=%.2f | threshold=%.2f | merchant=%s",
                confidence,
                DOCUMENT_AI_CONFIDENCE_THRESHOLD,
                docai_result.get("merchant_name"),
            )
            if confidence >= DOCUMENT_AI_CONFIDENCE_THRESHOLD:
                result = _docai_result_to_extraction_result(docai_result, confidence)
                docai_used = True
                logger.info(
                    "[extraction] Using Document AI result (confidence %.2f >= %.2f)",
                    confidence,
                    DOCUMENT_AI_CONFIDENCE_THRESHOLD,
                )
            else:
                docai_skipped_reason = f"confidence {confidence:.2f} below threshold {DOCUMENT_AI_CONFIDENCE_THRESHOLD:.2f}"
                logger.info(
                    "[extraction] Document AI below threshold; will use Bedrock | %s",
                    docai_skipped_reason,
                )
    except Exception as e:
        docai_error = str(e)
        logger.warning("[extraction] Document AI failed: %s; falling back to Bedrock", e, exc_info=True)
        errors.append(f"Document AI failed: {e}")

    # When Doc AI confidence < threshold or Doc AI failed: one VLM call for fraud check + extraction.
    if result is None:
        logger.info(
            "[extraction] Bedrock fallback: calling | docai_used=%s | docai_error=%s | docai_skipped=%s",
            docai_used,
            docai_error,
            docai_skipped_reason,
        )
        try:
            result, rejection_reason = bedrock_fraud_and_extract(
                receipt_file_path,
                model_id=BEDROCK_MODEL_ID,
                region=BEDROCK_REGION,
                validity_confidence_threshold=FRAUD_CHECK_CONFIDENCE_THRESHOLD,
            )
            if rejection_reason is not None:
                logger.warning("[extraction] Bedrock: receipt validity failed | reason=%s", rejection_reason)
                errors.append(rejection_reason)
                audit_trail.append({
                    "step": "extraction",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "action": "receipt_validity_failed",
                    "reason": rejection_reason,
                    "status": "error",
                })
                return out
            logger.info(
                "[extraction] Bedrock: success | merchant=%s | confidence=%.2f",
                result.merchant_name if result else None,
                result.extraction_confidence if result else 0.0,
            )
        except Exception as e:
            logger.exception("[extraction] Bedrock fraud check and extraction failed: %s", e)
            errors.append(f"Bedrock fraud check and extraction failed: {e}")
            audit_trail.append({
                "step": "extraction",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "extraction_failed",
                "error": str(e),
                "status": "error",
            })
            return out

    if not result:
        logger.warning("[extraction] No result from Document AI or Bedrock; extraction failed")
        return out

    phone_raw = result.phone_number or ""
    user_name_raw = result.customer_name or ""
    phone = normalize_phone_number(phone_raw)
    user_name = (user_name_raw or "").strip()
    vendor_type = detect_vendor_type(result.merchant_name, result.order_number)
    line_items = result.line_items or []
    extracted_dict = result.to_state_dict()
    extracted_dict = apply_vendor_specific_parsing(extracted_dict, vendor_type)
    products = format_products_list(line_items)

    out["extracted_data"] = extracted_dict
    out["merchant_name"] = result.merchant_name
    out["purchase_date"] = result.purchase_date
    out["order_number"] = result.order_number
    out["total_amount"] = result.total_amount
    out["line_items"] = line_items
    out["products"] = products
    out["phone_number"] = phone
    out["user_name"] = user_name
    out["extraction_confidence"] = result.extraction_confidence
    out["vendor_type"] = vendor_type
    out["extraction_errors"] = []
    audit_trail.append({
        "step": "extraction",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "extracted",
        "merchant": result.merchant_name,
        "vendor_type": vendor_type,
        "confidence": result.extraction_confidence,
        "status": "success",
    })
    out["audit_trail"] = audit_trail
    logger.info(
        "[extraction] Step 2 completed successfully | merchant=%s | confidence=%.2f | vendor_type=%s",
        result.merchant_name,
        result.extraction_confidence,
        vendor_type,
    )
    return out
