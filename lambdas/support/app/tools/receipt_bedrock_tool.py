"""
Bedrock VLM calls for the `support` receipt proof pipeline.

Ports the single-call behavior from `devyansh-lambda/services/bedrock_vlm.py`:
`detect_image_type_fraud_extract`.
"""

import base64
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

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
- If the image is fake, AI-generated, or not one of the four types above: set "is_valid" to false, "validity_confidence" to your confidence, and "extraction" to null.
- "line_items" when present: each item must have "product_name" or "description", "quantity", "price", "amount".
- Use null for missing optional fields. Always include "extraction_confidence" (0-1) when extraction is present.
"""


def _extract_json_from_response(content: str) -> Dict[str, Any]:
    """Extract JSON from model response (may be wrapped in markdown)."""
    m = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", content, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"\\{.*\\}", content, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    return json.loads(content)


def detect_image_type_fraud_extract(
    image_path: str,
    model_id: str,
    region: Optional[str] = None,
    validity_confidence_threshold: float = 0.8,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    One VLM call: (1) classify image type (order_receipt|order_id|review|selfie),
    (2) fraud/validity check, (3) type-specific extraction.

    Returns (result_dict, rejection_reason).
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    media_type = get_media_type(image_path)

    kwargs: Dict[str, Any] = {}
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

    rejection_reason: Optional[str] = None
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

