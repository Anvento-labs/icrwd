"""
Shared ExtractionResult and parsing helpers for receipt data.
Aligned with receipt_verification_agent semantics; reimplemented for iCrwd.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class ExtractionResult:
    """Standardized result structure from Document AI or Bedrock VLM."""
    merchant_name: Optional[str]
    purchase_date: Optional[str]  # YYYY-MM-DD
    order_number: Optional[str]
    total_amount: Optional[float]
    tax_amount: Optional[float]
    place: Optional[str]
    line_items: List[Dict[str, Any]]
    phone_number: Optional[str]
    customer_name: Optional[str]
    address: Optional[str]
    extraction_confidence: float
    raw_response: Optional[Dict[str, Any]] = None

    def to_state_dict(self) -> Dict[str, Any]:
        """Flatten to state-friendly dict (JSON-serializable)."""
        return {
            "merchant_name": self.merchant_name,
            "purchase_date": self.purchase_date,
            "order_number": self.order_number,
            "total_amount": self.total_amount,
            "tax_amount": self.tax_amount,
            "place": self.place,
            "line_items": self.line_items or [],
            "phone_number": self.phone_number,
            "customer_name": self.customer_name,
            "address": self.address,
            "extraction_confidence": self.extraction_confidence,
            "raw_response": self.raw_response,
        }


def normalize_phone_number(phone: str) -> str:
    """Normalize phone to E.164-style (US)."""
    if not phone:
        return ""
    import re
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits[0] == "1":
        return f"+1{digits[1:]}"
    if len(digits) == 10:
        return f"+1{digits}"
    return phone


def detect_vendor_type(merchant_name: Optional[str], order_number: Optional[str] = None) -> str:
    """Detect vendor: target, amazon, sprouts, unknown."""
    merchant_lower = (merchant_name or "").lower()
    if "target" in merchant_lower:
        if order_number and len(order_number) == 15 and (
            order_number.startswith("902") or order_number.startswith("912")
        ):
            return "target"
        return "target"
    if "amazon" in merchant_lower:
        return "amazon"
    if "sprouts" in merchant_lower:
        return "sprouts"
    return "unknown"


def format_products_list(line_items: List[Dict[str, Any]], max_products: int = 4) -> List[str]:
    """Format line items to Product 1..N list (up to max_products)."""
    products = []
    for item in (line_items or [])[:max_products]:
        name = item.get("product_name") or item.get("description") or ""
        if name:
            products.append(name)
    while len(products) < max_products:
        products.append("")
    return products


def apply_vendor_specific_parsing(
    extracted_data: Dict[str, Any], vendor_type: str
) -> Dict[str, Any]:
    """Apply vendor-specific rules (e.g. Target order number validation)."""
    enhanced = extracted_data.copy()
    if vendor_type == "target":
        order_number = extracted_data.get("order_number", "")
        if order_number:
            if len(order_number) == 15 and (
                order_number.startswith("902") or order_number.startswith("912")
            ):
                enhanced["order_number_valid"] = True
            else:
                enhanced["order_number_valid"] = False
                enhanced["order_number_error"] = (
                    "Target order number must be 15 digits starting with 902 or 912"
                )
    return enhanced
