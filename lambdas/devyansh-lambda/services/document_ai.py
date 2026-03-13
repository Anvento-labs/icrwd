"""
Google Document AI client for receipt extraction.
TODO: set GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_CLOUD_PROJECT, DOCUMENT_AI_PROCESSOR_ID in Lambda env.
"""

import logging
import os
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid failure when credentials not set
_documentai = None


def _get_documentai():
    global _documentai
    if _documentai is None:
        try:
            from google.cloud import documentai as dai
            _documentai = dai
            logger.info("[document_ai] google-cloud-documentai loaded successfully")
        except Exception as e:
            logger.warning("[document_ai] google-cloud-documentai not available: %s", e)
            return None
    return _documentai


def extract_receipt(
    image_path: str,
    project_id: str,
    location: str,
    processor_id: str,
) -> Dict[str, Any]:
    """
    Extract receipt data using Google Document AI Expense/Receipt processor.

    Args:
        image_path: Local path to image file
        project_id: Google Cloud project ID
        location: Processor location (e.g. "us")
        processor_id: Document AI processor ID

    Returns:
        Dict with merchant_name, purchase_date, order_number, total_amount, tax_amount,
        place, line_items, phone_number, customer_name, address, extraction_confidence,
        raw_document_ai (optional).

    Raises:
        ValueError: If Document AI client or processor not available
        Exception: On API failure
    """
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    logger.info(
        "[document_ai] extract_receipt called | image_path=%s | project_id=%s | location=%s | processor_id=%s | GOOGLE_APPLICATION_CREDENTIALS=%s",
        image_path,
        project_id,
        location,
        processor_id,
        creds_path or "(not set)",
    )

    dai = _get_documentai()
    if not dai:
        msg = (
            "Google Document AI not available. "
            "Install google-cloud-documentai and set GOOGLE_APPLICATION_CREDENTIALS."
        )
        logger.error("[document_ai] %s", msg)
        raise ValueError(msg)

    client = dai.DocumentProcessorServiceClient()
    processor_name = client.processor_path(project_id, location, processor_id)
    logger.info("[document_ai] processor_name=%s | calling process_document", processor_name)

    with open(image_path, "rb") as f:
        image_content = f.read()
    image_size = len(image_content)
    logger.info("[document_ai] read image | size_bytes=%s", image_size)

    mime_type = "image/jpeg"
    if image_path.lower().endswith(".png"):
        mime_type = "image/png"
    elif image_path.lower().endswith(".pdf"):
        mime_type = "application/pdf"

    raw_document = dai.RawDocument(content=image_content, mime_type=mime_type)
    request = dai.ProcessRequest(name=processor_name, raw_document=raw_document)
    try:
        response = client.process_document(request=request)
    except Exception as e:
        logger.exception(
            "[document_ai] process_document failed | error=%s | type=%s",
            e,
            type(e).__name__,
        )
        raise

    document = response.document
    entity_count = len(document.entities) if document and hasattr(document, "entities") else 0
    logger.info("[document_ai] process_document success | entities=%s", entity_count)

    return _parse_document_ai_response(document)


def _get_text_from_anchor(text_anchor, full_text: str) -> str:
    """Extract text from Document AI TextAnchor."""
    if not text_anchor or not full_text:
        return ""
    if hasattr(text_anchor, "content") and text_anchor.content:
        return (text_anchor.content or "").strip()
    if not hasattr(text_anchor, "text_segments") or not text_anchor.text_segments:
        return ""
    segs = text_anchor.text_segments
    start = getattr(segs[0], "start_index", None)
    if start is None:
        start = 0
    end = getattr(segs[-1], "end_index", None)
    if end is None:
        end = len(full_text)
    return full_text[int(start) : int(end)]


def _get_text_from_layout(layout, full_text: str) -> str:
    """Extract text from layout (has .text_anchor) or TextAnchor."""
    if not layout:
        return ""
    if hasattr(layout, "text_segments"):
        return _get_text_from_anchor(layout, full_text)
    if hasattr(layout, "text_anchor") and layout.text_anchor:
        return _get_text_from_anchor(layout.text_anchor, full_text)
    return ""


def _parse_line_item_text(text: str) -> Dict[str, Any]:
    """Parse line_item text like 'SMOOTH LEGEND SHAVE\\n15.99' -> description, amount, quantity."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {"description": text, "amount": None, "quantity": 1}
    amount = None
    description_parts = []
    for i, part in enumerate(lines):
        m = re.match(r"^([\d,]+\.?\d*)\s*[TM]?$", part)
        if m:
            try:
                amount = float(m.group(1).replace(",", ""))
                description_parts = lines[:i]
                break
            except ValueError:
                description_parts.append(part)
        else:
            description_parts.append(part)
    description = " ".join(description_parts).strip() if description_parts else text
    return {"description": description or text, "amount": amount, "quantity": 1}


def _parse_document_ai_response(document) -> Dict[str, Any]:
    """Parse Document AI document to our extraction dict."""
    entities = {}
    full_text = document.text or ""

    for entity in document.entities:
        entity_type = getattr(entity, "type_", "") or ""
        normalized_value = getattr(entity, "normalized_value", None)

        entity_text = ""
        if hasattr(entity, "text_anchor") and entity.text_anchor:
            entity_text = _get_text_from_layout(entity.text_anchor, full_text)
        elif hasattr(entity, "mention_text"):
            entity_text = entity.mention_text or ""

        if entity_type in ["merchant_name", "supplier_name", "vendor_name"]:
            entities["merchant_name"] = entity_text
        elif entity_type in ["receipt_date", "invoice_date", "transaction_date"]:
            if normalized_value and hasattr(normalized_value, "date_value"):
                dv = normalized_value.date_value
                entities["purchase_date"] = f"{dv.year}-{dv.month:02d}-{dv.day:02d}"
            else:
                entities["purchase_date"] = entity_text
        elif entity_type in ["receipt_id", "invoice_id", "transaction_id"]:
            entities["order_number"] = entity_text
        elif entity_type in ["total_amount", "total_price", "total"]:
            if normalized_value and hasattr(normalized_value, "money_value"):
                money = normalized_value.money_value
                entities["total_amount"] = float(money.units or 0) + (
                    float(money.nanos or 0) / 1e9
                )
            else:
                try:
                    entities["total_amount"] = float(
                        entity_text.replace("$", "").replace(",", "").strip()
                    )
                except (ValueError, AttributeError):
                    pass
        elif entity_type in ["tax_amount", "tax", "gst", "vat"]:
            if normalized_value and hasattr(normalized_value, "money_value"):
                money = normalized_value.money_value
                entities["tax_amount"] = float(money.units or 0) + (
                    float(money.nanos or 0) / 1e9
                )
            else:
                try:
                    entities["tax_amount"] = float(
                        entity_text.replace("$", "").replace(",", "").strip()
                    )
                except (ValueError, AttributeError):
                    pass
        elif entity_type in ["merchant_address", "supplier_address", "vendor_address"]:
            entities["address"] = entity_text
        elif entity_type in ["merchant_phone_number", "supplier_phone", "phone"]:
            entities["phone_number"] = entity_text

    line_items = []
    for entity in document.entities:
        if (getattr(entity, "type_", "") or "") != "line_item":
            continue
        entity_text = ""
        if hasattr(entity, "text_anchor") and entity.text_anchor:
            entity_text = _get_text_from_layout(entity.text_anchor, full_text)
        elif hasattr(entity, "mention_text"):
            entity_text = entity.mention_text or ""
        if not entity_text or not entity_text.strip():
            continue
        parsed = _parse_line_item_text(entity_text.strip())
        if parsed.get("amount") is not None or parsed.get("description"):
            line_items.append({
                "product_name": parsed.get("description", ""),
                "description": parsed.get("description", ""),
                "sku": None,
                "quantity": parsed.get("quantity", 1),
                "price": parsed.get("amount") if parsed.get("amount") is not None else 0.0,
                "amount": parsed.get("amount") if parsed.get("amount") is not None else 0.0,
            })

    confidences = []
    for entity in document.entities:
        if hasattr(entity, "confidence") and entity.confidence is not None:
            confidences.append(float(entity.confidence))
    overall_confidence = sum(confidences) / len(confidences) if confidences else 0.8

    place = entities.get("merchant_name")
    for entity in document.entities:
        et = getattr(entity, "type_", "") or ""
        if et in ["merchant_location", "store_location", "place"]:
            entity_text = ""
            if hasattr(entity, "text_anchor") and entity.text_anchor:
                entity_text = _get_text_from_layout(entity.text_anchor, full_text)
            elif hasattr(entity, "mention_text"):
                entity_text = entity.mention_text or ""
            if entity_text:
                place = entity_text
                break

    return {
        "merchant_name": entities.get("merchant_name"),
        "purchase_date": entities.get("purchase_date"),
        "order_number": entities.get("order_number"),
        "total_amount": entities.get("total_amount"),
        "tax_amount": entities.get("tax_amount"),
        "place": place,
        "line_items": line_items,
        "phone_number": entities.get("phone_number"),
        "customer_name": None,
        "address": entities.get("address"),
        "extraction_confidence": overall_confidence,
        "raw_document_ai": {
            "text": (full_text[:1000] if full_text else ""),
            "entity_count": len(document.entities),
        },
    }


def is_available(project_id: Optional[str] = None, processor_id: Optional[str] = None) -> bool:
    """Check if Document AI is configured (project + processor)."""
    if not project_id:
        logger.info("[document_ai] is_available=False | reason=missing project_id")
        return False
    if not processor_id:
        logger.info("[document_ai] is_available=False | reason=missing processor_id")
        return False
    if _get_documentai() is None:
        logger.info("[document_ai] is_available=False | reason=google-cloud-documentai library not available")
        return False
    logger.info("[document_ai] is_available=True | project_id=%s | processor_id=%s", project_id, processor_id)
    return True
