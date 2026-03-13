"""
AWS Bedrock VLM for receipt extraction (fallback when Document AI confidence is low).
Option A: When Doc AI confidence < 80%%, one VLM call does both fraud check + extraction.
Uses Lambda execution role. Model id from config.
"""

import base64
import json
import logging
import re
from typing import Dict, Any, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from .extraction_schema import ExtractionResult

logger = logging.getLogger(__name__)


def get_media_type(file_path: str) -> str:
    """Get media type from file extension."""
    ext = (file_path or "").lower().split(".")[-1]
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")


EXTRACTION_PROMPT = """Extract the following information from this receipt image and return ONLY valid JSON (no markdown, no code blocks):

{
    "merchant_name": "string",
    "purchase_date": "YYYY-MM-DD",
    "order_number": "string or null",
    "total_amount": float,
    "tax_amount": float or null,
    "place": "string or null",
    "address": "string or null",
    "line_items": [
        {
            "product_name": "string",
            "description": "string",
            "sku": "string or null",
            "quantity": int,
            "price": float,
            "amount": float
        }
    ],
    "phone_number": "string or null",
    "customer_name": "string or null",
    "extraction_confidence": float (0-1)
}

Important:
- "tax_amount": Extract tax if visible
- "place": Merchant/store location
- "line_items": Each item must include "description" and "amount" (line total)
"""

# Combined prompt: (1) fraud/validity check, (2) extraction if valid. One VLM call.
FRAUD_AND_EXTRACTION_PROMPT = """You must answer with a single JSON object (no markdown, no code blocks).

Step 1 - Receipt validity: Is this image a REAL retail/purchase receipt (paper or digital)? It must NOT be AI-generated, fake, or a random non-receipt image. Consider: Does it look like a genuine receipt from a store with merchant name, items, prices, total, and date?

Step 2 - If and only if the image is a valid receipt, extract the receipt data.

Return exactly this JSON structure:
{
    "is_valid_receipt": true or false,
    "receipt_validity_confidence": 0.0 to 1.0,
    "extraction": {
        "merchant_name": "string",
        "purchase_date": "YYYY-MM-DD",
        "order_number": "string or null",
        "total_amount": float,
        "tax_amount": float or null,
        "place": "string or null",
        "address": "string or null",
        "line_items": [
            {
                "product_name": "string",
                "description": "string",
                "sku": "string or null",
                "quantity": int,
                "price": float,
                "amount": float
            }
        ],
        "phone_number": "string or null",
        "customer_name": "string or null",
        "extraction_confidence": float (0-1)
    }
}

Rules:
- If the image is NOT a valid receipt (fake, AI-generated, or not a receipt): set "is_valid_receipt" to false, "receipt_validity_confidence" to your confidence in that, and "extraction" to null or omit it.
- If the image IS a valid receipt: set "is_valid_receipt" to true, "receipt_validity_confidence" to your confidence, and "extraction" with all fields above.
- "line_items": each item must have "description" and "amount" (line total).
"""

# Detect image type + fraud + extract (4 types: order_receipt, order_id, review, selfie)
DETECT_TYPE_FRAUD_EXTRACT_PROMPT = """You must answer with a single JSON object (no markdown, no code blocks).

Step 1 - Classify the image type. Exactly one of:
- "order_receipt": Photo of a paper or digital receipt from a store (merchant name, items, prices, total, date).
- "order_id": Screenshot of an online order (e.g. Amazon, Target, Walmart) with order number, product names, amount, date.
- "review": Screenshot of a product review (stars, reviewer name, date, product name, review text).
- "selfie": Photo of a person (face/body), e.g. attendance proof at an event.

Step 2 - Validity: Is this image genuine (NOT AI-generated, fake, or heavily edited)? Assign a confidence 0.0 to 1.0.

Step 3 - If valid, extract data according to type. If invalid, set "extraction" to null.

Return exactly this JSON structure:
{
    "image_type": "order_receipt" | "order_id" | "review" | "selfie",
    "is_valid": true or false,
    "validity_confidence": 0.0 to 1.0,
    "extraction": {
        (for order_receipt: merchant_name, purchase_date, order_number, total_amount, tax_amount, place, line_items, extraction_confidence)
        (for order_id: order_id, merchant_name, order_date, total_amount, product_names, extraction_confidence)
        (for review: product_name, reviewer_name, review_date, stars, review_text, extraction_confidence)
        (for selfie: extraction_confidence only, or null)
    } or null
}

Rules:
- If the image is fake, AI-generated, or not one of the four types above: set "is_valid" to false, "validity_confidence" to your confidence, "extraction" to null.
- "line_items" when present: each item must have "product_name" or "description", "quantity", "price", "amount".
- Use null for missing optional fields. Always include "extraction_confidence" (0-1) when extraction is present.
"""


def detect_image_type_fraud_extract(
    image_path: str,
    model_id: str,
    region: Optional[str] = None,
    validity_confidence_threshold: float = 0.8,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    One VLM call: (1) Classify image type (order_receipt, order_id, review, selfie),
    (2) Fraud/validity check, (3) Type-specific extraction.
    Returns (result_dict, rejection_reason).
    result_dict: detected_image_type, is_valid_image, validity_confidence, extracted_data (dict or None), detection_rejection_reason.
    rejection_reason: non-None if invalid or confidence below threshold.
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    media_type = get_media_type(image_path)

    kwargs = {}
    if region:
        kwargs["region_name"] = region
    runtime = boto3.client("bedrock-runtime", **kwargs)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_image,
                        },
                    },
                    {"type": "text", "text": DETECT_TYPE_FRAUD_EXTRACT_PROMPT},
                ],
            }
        ],
    }

    try:
        response = runtime.invoke_model(modelId=model_id, body=json.dumps(body))
    except ClientError as e:
        logger.error("[detect_image] Bedrock invoke_model failed: %s", e)
        return (
            {
                "detected_image_type": None,
                "is_valid_image": False,
                "validity_confidence": 0.0,
                "extracted_data": None,
                "detection_rejection_reason": f"Model invocation failed: {e}",
            },
            f"Model invocation failed: {e}",
        )

    response_body = json.loads(response["body"].read())
    content = response_body.get("content", [{}])[0].get("text", "{}")
    data = _extract_json_from_response(content)

    image_type = (data.get("image_type") or "").strip().lower()
    if image_type not in ("order_receipt", "order_id", "review", "selfie"):
        image_type = "order_receipt"  # fallback

    is_valid = bool(data.get("is_valid", False))
    validity_conf = float(data.get("validity_confidence", 0.0))
    extraction = data.get("extraction")
    if extraction is not None and not isinstance(extraction, dict):
        extraction = None

    rejection_reason = None
    if not is_valid:
        rejection_reason = "Image did not pass validity check (possible fake or not an accepted proof type)."
    elif validity_conf < validity_confidence_threshold:
        rejection_reason = f"Validity confidence ({validity_conf:.2f}) below threshold ({validity_confidence_threshold})."

    result = {
        "detected_image_type": image_type,
        "is_valid_image": is_valid and validity_conf >= validity_confidence_threshold,
        "validity_confidence": validity_conf,
        "extracted_data": extraction,
        "detection_rejection_reason": rejection_reason,
    }
    logger.info(
        "[detect_image] type=%s | is_valid=%s | confidence=%.2f | has_extraction=%s",
        image_type,
        result["is_valid_image"],
        validity_conf,
        extraction is not None,
    )
    return result, rejection_reason if not result["is_valid_image"] else None


def extract_receipt_with_fraud_check(
    image_path: str,
    model_id: str,
    region: Optional[str] = None,
    validity_confidence_threshold: float = 0.8,
) -> Tuple[Optional[ExtractionResult], Optional[str]]:
    """
    One VLM call: (1) Is this a real receipt? (2) If yes, extract data.
    When Doc AI confidence is low, use this instead of extract_receipt to avoid a separate fraud call.

    Returns:
        (ExtractionResult, None) if valid receipt and extraction succeeded.
        (None, rejection_reason) if not a valid receipt or validity confidence too low.
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    media_type = get_media_type(image_path)

    kwargs = {}
    if region:
        kwargs["region_name"] = region
    runtime = boto3.client("bedrock-runtime", **kwargs)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_image,
                        },
                    },
                    {"type": "text", "text": FRAUD_AND_EXTRACTION_PROMPT},
                ],
            }
        ],
    }

    response = runtime.invoke_model(modelId=model_id, body=json.dumps(body))
    response_body = json.loads(response["body"].read())
    content = response_body["content"][0]["text"]
    data = _extract_json_from_response(content)

    is_valid = data.get("is_valid_receipt", False)
    validity_conf = float(data.get("receipt_validity_confidence", 0.0))

    if not is_valid:
        return (
            None,
            "Receipt validity check failed: image is not a valid receipt (possible fake or AI-generated).",
        )
    if validity_conf < validity_confidence_threshold:
        return (
            None,
            f"Receipt validity confidence ({validity_conf:.2f}) below threshold ({validity_confidence_threshold}).",
        )

    extraction = data.get("extraction")
    if not extraction or not isinstance(extraction, dict):
        return (None, "Valid receipt but extraction missing or invalid.")

    line_items = []
    for item in extraction.get("line_items", []):
        line_items.append({
            "product_name": item.get("product_name", ""),
            "description": item.get("description", item.get("product_name", "")),
            "sku": item.get("sku"),
            "quantity": item.get("quantity", 1),
            "price": item.get("price", 0.0),
            "amount": item.get("amount", item.get("price", 0.0) * item.get("quantity", 1)),
        })

    return (
        ExtractionResult(
            merchant_name=extraction.get("merchant_name"),
            purchase_date=extraction.get("purchase_date"),
            order_number=extraction.get("order_number"),
            total_amount=extraction.get("total_amount"),
            tax_amount=extraction.get("tax_amount"),
            place=extraction.get("place"),
            line_items=line_items,
            phone_number=extraction.get("phone_number"),
            customer_name=extraction.get("customer_name"),
            address=extraction.get("address"),
            extraction_confidence=float(extraction.get("extraction_confidence", validity_conf)),
            raw_response={
                "model": model_id,
                "usage": response_body.get("usage", {}),
                "fraud_check": "passed",
                "receipt_validity_confidence": validity_conf,
            },
        ),
        None,
    )


def extract_receipt(
    image_path: str,
    model_id: str,
    region: Optional[str] = None,
) -> ExtractionResult:
    """
    Extract receipt data using AWS Bedrock VLM (e.g. Claude).

    Args:
        image_path: Local path to image file
        model_id: Bedrock model ID (e.g. anthropic.claude-3-5-sonnet-20241022-v2:0)
        region: AWS region (optional)

    Returns:
        ExtractionResult with standardized fields

    Raises:
        ClientError: On Bedrock API failure
        ValueError: On parse failure
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    media_type = get_media_type(image_path)

    kwargs = {}
    if region:
        kwargs["region_name"] = region
    runtime = boto3.client("bedrock-runtime", **kwargs)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_image,
                        },
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    }

    response = runtime.invoke_model(modelId=model_id, body=json.dumps(body))
    response_body = json.loads(response["body"].read())
    content = response_body["content"][0]["text"]
    data = _extract_json_from_response(content)

    line_items = []
    for item in data.get("line_items", []):
        line_items.append({
            "product_name": item.get("product_name", ""),
            "description": item.get("description", item.get("product_name", "")),
            "sku": item.get("sku"),
            "quantity": item.get("quantity", 1),
            "price": item.get("price", 0.0),
            "amount": item.get("amount", item.get("price", 0.0) * item.get("quantity", 1)),
        })

    return ExtractionResult(
        merchant_name=data.get("merchant_name"),
        purchase_date=data.get("purchase_date"),
        order_number=data.get("order_number"),
        total_amount=data.get("total_amount"),
        tax_amount=data.get("tax_amount"),
        place=data.get("place"),
        line_items=line_items,
        phone_number=data.get("phone_number"),
        customer_name=data.get("customer_name"),
        address=data.get("address"),
        extraction_confidence=float(data.get("extraction_confidence", 0.0)),
        raw_response={"model": model_id, "usage": response_body.get("usage", {})},
    )


def _extract_json_from_response(content: str) -> Dict[str, Any]:
    """Extract JSON from model response (may be wrapped in markdown)."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    return json.loads(content)
