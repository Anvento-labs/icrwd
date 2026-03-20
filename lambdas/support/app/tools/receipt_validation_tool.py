"""
Receipt validation logic for the `support` receipt proof pipeline.

Ports the active validation path from:
`lambdas/devyansh-lambda/steps/step3_validation.py`

Differences vs devyansh-lambda:
- No BYPASS_VALIDATION path (disabled by design).
- Uses `app.receipt_config` and `app.tools.receipt_mongo_tool`.
"""

import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app.receipt_config import (
    MONGODB_URI,
    MONGODB_DATABASE,
    MONGODB_CRWDS_COLLECTION,
    MONGODB_CAMPAIGN_RULES_COLLECTION,
    MONGODB_USERS_COLLECTION,
    MONGODB_BLOCK_USERS_COLLECTION,
    MONGODB_ADDED_WORKER_CRWD_MEMBERS_COLLECTION,
    MONGODB_ORDER_RECEIPT_REVIEWS_COLLECTION,
)
from app.tools.receipt_mongo_tool import (
    find_crwd_by_merchant_name,
    get_user,
    is_user_blocked,
    is_worker_in_campaign,
    get_campaign_rules,
    order_number_used_in_campaign,
)

logger = logging.getLogger(__name__)


def _fuzzy_match_product(product_name: str, target_name: str, threshold: float = 0.90) -> tuple[bool, float]:
    if not product_name or not target_name:
        return False, 0.0
    a = " ".join(product_name.lower().split())
    b = " ".join(target_name.lower().split())
    similarity = SequenceMatcher(None, a, b).ratio()
    return similarity >= threshold, similarity


def _validate_merchant(merchant_name: str, valid_merchants: List[str]) -> tuple[bool, str]:
    if not merchant_name:
        return False, "Merchant name not found in receipt"
    merchant_lower = merchant_name.lower()
    for v in valid_merchants:
        if v.lower() in merchant_lower or merchant_lower in v.lower():
            return True, ""
    return False, f"Merchant '{merchant_name}' is not valid for this campaign. Valid: {', '.join(valid_merchants)}"


def _parse_purchase_date(purchase_date: Any) -> Optional[datetime]:
    """Parse receipt purchase date. US receipts: various formats (MM-DD-YY, MM/DD/YYYY, etc.)."""
    if purchase_date is None:
        return None
    if isinstance(purchase_date, datetime):
        return purchase_date

    s = str(purchase_date).strip()
    if not s:
        return None

    # US date formats: try 4-digit year first, then 2-digit year (YY = 2000-2068, 69-99 = 1969-1999)
    formats_4digit = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]
    formats_2digit = ["%m-%d-%y", "%m/%d/%y", "%d-%m-%y", "%d/%m/%y"]

    for fmt in formats_4digit:
        try:
            return datetime.strptime(s[:10], fmt)
        except ValueError:
            continue

    # 2-digit year: use up to 8 chars (MM-DD-YY) or 10 if longer
    s_short = s[:10] if len(s) >= 10 else s
    for fmt in formats_2digit:
        try:
            return datetime.strptime(s_short, fmt)
        except ValueError:
            continue

    # Month name: "November 30, 2025" or "Nov 30, 2025"
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s[:30].strip(), fmt)
        except ValueError:
            continue

    return None


def _date_range_from_crwd(crwd: Dict[str, Any]) -> Dict[str, str]:
    start_date = crwd.get("start_date")
    end_date = crwd.get("end_date")
    if hasattr(start_date, "strftime"):
        start_date = start_date.strftime("%Y-%m-%d")
    else:
        start_date = str(start_date)[:10] if start_date else ""

    if hasattr(end_date, "strftime"):
        end_date = end_date.strftime("%Y-%m-%d")
    else:
        end_date = str(end_date)[:10] if end_date else ""

    return {"start_date": start_date or "1970-01-01", "end_date": end_date or "2099-12-31"}


def _validate_date(purchase_date: Any, date_range: Dict[str, str]) -> tuple[bool, str]:
    if not date_range or not date_range.get("start_date") or not date_range.get("end_date"):
        return True, ""

    dt = _parse_purchase_date(purchase_date)
    if not dt:
        return False, "Purchase date not found in receipt"

    try:
        start = datetime.strptime(date_range["start_date"], "%Y-%m-%d")
        end = datetime.strptime(date_range["end_date"], "%Y-%m-%d")
    except (ValueError, KeyError):
        return True, ""

    if start <= dt <= end:
        return True, ""
    return False, f"Purchase date {dt.strftime('%Y-%m-%d')} is outside campaign date range ({date_range['start_date']} to {date_range['end_date']})"


def _validate_products(
    line_items: List[Dict[str, Any]],
    required_products: List[Dict[str, Any]],
    optional_products: Optional[List[Dict[str, Any]]] = None,
) -> tuple[bool, List[str], float]:
    violations: List[str] = []
    match_scores: List[float] = []

    # Note: optional_products is currently unused in the devyansh implementation for product validation.
    _ = optional_products

    for rp in required_products:
        name = rp.get("name", "")
        sku = rp.get("sku")
        fuzzy_match = rp.get("fuzzy_match", True)
        min_quantity = rp.get("min_quantity", 1)

        found = False
        found_quantity = 0
        best = 0.0

        for li in line_items:
            item_name = li.get("product_name", "")
            item_sku = li.get("sku", "")
            item_qty = li.get("quantity", 1)

            if sku and item_sku and sku.lower() == item_sku.lower():
                found = True
                found_quantity += item_qty
                best = 1.0
                continue

            if fuzzy_match:
                ok, sim = _fuzzy_match_product(item_name, name)
                if ok:
                    found = True
                    found_quantity += item_qty
                    best = max(best, sim)
            else:
                if name.lower() in item_name.lower() or item_name.lower() in name.lower():
                    found = True
                    found_quantity += item_qty
                    best = 1.0

        if found:
            match_scores.append(best)
            if found_quantity < min_quantity:
                violations.append(f"Required product '{name}' quantity ({found_quantity}) < min ({min_quantity})")
        else:
            violations.append(f"Required product '{name}' not found in receipt")

    overall = sum(match_scores) / len(match_scores) if match_scores else 0.0
    return len(violations) == 0, violations, overall


def _validate_vendor_rules(
    extracted_data: Dict[str, Any],
    vendor_type: str,
    vendor_rules: Dict[str, Any],
) -> tuple[bool, List[str]]:
    violations: List[str] = []
    if vendor_type not in vendor_rules:
        return True, []

    rules = vendor_rules[vendor_type]
    if "order_number_pattern" in rules:
        order_number = extracted_data.get("order_number", "")
        pattern = rules["order_number_pattern"]
        if rules.get("required", False) and not order_number:
            violations.append(f"{vendor_type.capitalize()} order number required but not found")
        elif order_number and not re.match(pattern, order_number):
            violations.append(f"{vendor_type.capitalize()} order number does not match pattern")

    return len(violations) == 0, violations


def _calculate_validation_score(validation_results: List[Dict[str, Any]]) -> float:
    if not validation_results:
        return 0.0

    n = len(validation_results)
    passed = sum(1 for r in validation_results if r.get("passed", False))
    base = (passed / n) * 100

    confs = [r.get("confidence", 0.0) for r in validation_results if r.get("confidence") is not None]
    if confs:
        avg = sum(confs) / len(confs)
        return round((base * 0.7) + (avg * 100 * 0.3), 2)
    return round(base, 2)


def _determine_final_decision(validation_score: float, violations: List[str], extraction_confidence: float) -> tuple[str, bool, str]:
    has_critical = any("merchant" in v.lower() or "date" in v.lower() for v in violations)
    if has_critical or validation_score < 50:
        return "REJECTED", False, "; ".join(violations[:3])

    if validation_score >= 90 and extraction_confidence >= 0.85 and not violations:
        return "APPROVED", False, ""

    reasons: List[str] = []
    if validation_score < 90:
        reasons.append(f"Validation score ({validation_score}) below 90")
    if extraction_confidence < 0.85:
        reasons.append(f"Extraction confidence ({extraction_confidence:.2f}) below 0.85")
    if violations:
        reasons.append(f"{len(violations)} validation issue(s)")
    return "PENDING_REVIEW", True, "; ".join(reasons)


def _fail(out: Dict[str, Any], audit_trail: List[Dict[str, Any]], review_reason: str, action: str) -> Dict[str, Any]:
    """Append audit entry and set review_reason and reply_message; return out."""
    logger.warning("validation_fail | action=%s | review_reason=%s", action, review_reason)
    audit_trail.append(
        {
            "step": "validation",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "reason": review_reason,
            "status": "error",
        }
    )
    out["review_reason"] = review_reason
    out["reply_message"] = review_reason
    out["audit_trail"] = audit_trail
    return out


def _build_reply_message(
    final_decision: str,
    validation_status: str,
    review_reason: str,
    campaign_name: str,
    validation_score: float,
    violations: Optional[List[str]] = None,
) -> str:
    """Build user-facing reply from validation result."""
    if final_decision == "APPROVED":
        parts = ["Receipt approved."]
        if campaign_name:
            parts.append(f"Campaign: {campaign_name}.")
        if validation_score is not None:
            parts.append(f"Score: {validation_score:.0%}.")
        return " ".join(parts)

    if final_decision == "REJECTED" and review_reason:
        return review_reason

    if validation_status == "pending_review" or final_decision == "PENDING_REVIEW":
        # User-friendly message only: what's missing, not technical score/count
        if violations:
            product_names: List[str] = []
            seen_names: set[str] = set()
            for v in violations:
                if not v:
                    continue
                if "Required product '" in v and "' not found" in v:
                    start = v.find("'") + 1
                    end = v.find("'", start)
                    if end > start:
                        name = v[start:end]
                        if name and name not in seen_names:
                            seen_names.add(name)
                            product_names.append(name)
                elif v not in seen_names:
                    seen_names.add(v)
                    product_names.append(v)

            if product_names:
                names_str = ", ".join(product_names[:5])
                msg = f"Missing these products: {names_str}. Please upload the correct receipt."
                if campaign_name:
                    msg += f" Campaign: {campaign_name}."
                return msg

        return "Receipt is under review. Please upload the correct receipt." + (
            f" Campaign: {campaign_name}." if campaign_name else ""
        )

    return review_reason or "Validation completed."


def _normalize_product_name(name: str) -> str:
    """Normalize product/store name for matching: lowercase, strip, collapse spaces."""
    if not name:
        return ""
    return " ".join(str(name).lower().strip().split())


def _select_store_for_merchant(
    gig_stores: List[Dict[str, Any]],
    merchant_name: str,
    min_similarity: float = 0.7,
) -> tuple[Optional[Dict[str, Any]], float]:
    """Pick a single gig_store from rules.gig_stores based on merchant_name."""
    if not gig_stores or not merchant_name:
        return None, 0.0

    merchant_norm = _normalize_product_name(merchant_name)
    best_store: Optional[Dict[str, Any]] = None
    best_score = 0.0
    second_best = 0.0

    for store in gig_stores:
        store_name = store.get("store_name") or ""
        store_norm = store.get("normalized_store_name") or _normalize_product_name(store_name)
        if not store_norm:
            continue
        score = SequenceMatcher(None, merchant_norm, store_norm).ratio()
        if score > best_score:
            second_best = best_score
            best_score = score
            best_store = store
        elif score > second_best:
            second_best = score

    # Require a clear best match above threshold and not tied too closely with second best
    if not best_store or best_score < min_similarity or (second_best and (best_score - second_best) < 0.05):
        return None, best_score
    return best_store, best_score


def _validate_store_products(
    line_items: List[Dict[str, Any]],
    store_products: List[Dict[str, Any]],
) -> tuple[bool, List[str], float, List[str]]:
    """
    Validate that all configured store_products are present in the receipt line_items.

    Returns (ok, violations, score, matched_products_names).
    """
    normalized_items: List[tuple[str, str]] = []  # (raw_name, normalized)
    for item in line_items or []:
        raw = item.get("product_name") or item.get("description") or ""
        norm = _normalize_product_name(raw)
        if norm:
            normalized_items.append((raw, norm))

    violations: List[str] = []
    matched_products: List[str] = []

    if not store_products:
        return True, violations, 1.0, matched_products

    total = 0
    for prod in store_products:
        name = prod.get("name") or ""
        norm_name = prod.get("normalized_product_name") or _normalize_product_name(name)
        if not norm_name:
            continue
        total += 1

        found = False
        for raw, norm in normalized_items:
            if norm == norm_name:
                found = True
                matched_products.append(name or raw)
                break
            # Allow simple contains when product name is reasonably long
            if len(norm_name) > 3 and norm_name in norm:
                found = True
                matched_products.append(name or raw)
                break

        if not found:
            violations.append(f"Required product '{name}' not found on receipt")

    if total == 0:
        return True, violations, 1.0, matched_products

    ok = not violations
    matched_count = total - len(violations)
    score = float(matched_count) / float(total)
    return ok, violations, score, matched_products


def _check_multiproof_pending(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    If campaign requires multiple proof types and we don't have all yet, return state update:
    pending_proof_types + reply_message + submitted_proofs (existing + current).
    """
    required = state.get("required_proof_types") or []
    if len(required) <= 1:
        return None

    submitted = list(state.get("submitted_proofs") or [])
    detected_type = state.get("detected_image_type")
    if detected_type and state.get("extracted_data") is not None:
        submitted.append(
            {
                "proof_type": detected_type,
                "extracted_data": state.get("extracted_data"),
                "receipt_s3_key": state.get("receipt_s3_key"),
            }
        )

    submitted_types = [p.get("proof_type") for p in submitted if p.get("proof_type")]
    pending = [t for t in required if t not in submitted_types]
    if not pending:
        return None

    detected_label = detected_type or "this image"
    n_total = len(required)
    n_done = len(submitted_types)
    n_more = len(pending)

    reply = (
        f"We believe the image you uploaded is a {detected_label.replace('_', ' ')}. "
        f"This campaign requires {n_total} proof type(s) in total. You have submitted {n_done}. "
        f"Please also upload: {', '.join(p.replace('_', ' ') for p in pending)} ({n_more} more). "
        f"Upload a {pending[0].replace('_', ' ')} image next."
    )

    return {
        "submitted_proofs": submitted,
        "pending_proof_types": pending,
        "reply_message": reply,
    }


def run_validation(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate receipt against campaign rules (MongoDB).

    Campaign is inferred from merchant name.
    """
    logger.info("Step validation: started")

    audit_trail: List[Dict[str, Any]] = list(state.get("audit_trail", []))
    out: Dict[str, Any] = {
        **state,
        "validation_status": "rejected",
        "final_decision": "REJECTED",
        "validation_score": 0.0,
        "validation_results": [],
        "violation_details": [],
        "requires_manual_review": False,
        "review_reason": None,
        "decision_confidence": state.get("extraction_confidence"),
        "audit_trail": audit_trail,
    }

    # 0. No extracted_data
    if not state.get("extracted_data"):
        logger.info("run_validation | step=0 | no extracted_data")
        return _fail(out, audit_trail, "Data extraction failed", "no_extracted_data")

    # 1. Merchant name
    merchant_name = (state.get("merchant_name") or "").strip()
    if not merchant_name:
        logger.info("run_validation | step=1 | merchant_name empty")
        return _fail(out, audit_trail, "Could not identify merchant from receipt", "no_merchant")

    if not MONGODB_URI:
        logger.warning("MONGODB_URI not set; skipping campaign validation")
        out["review_reason"] = "MongoDB not configured (TODO: set MONGODB_URI)"
        out["requires_manual_review"] = True
        audit_trail.append(
            {
                "step": "validation",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "skipped",
                "reason": "mongodb_not_configured",
                "status": "pending_review",
            }
        )
        out["audit_trail"] = audit_trail
        return out

    # 2. Find crwd by merchant name (fuzzy match)
    crwd, match_score = find_crwd_by_merchant_name(
        MONGODB_URI,
        MONGODB_DATABASE,
        MONGODB_CRWDS_COLLECTION,
        merchant_name,
        min_similarity=0.7,
    )
    if not crwd:
        return _fail(out, audit_trail, "No campaign found for this merchant", "no_matching_campaign")

    campaign_id = str(crwd.get("_id", ""))
    campaign_name = crwd.get("name", "")
    out["campaign_id"] = campaign_id
    out["campaign_name"] = campaign_name
    logger.info(
        "run_validation | step=2 | campaign_resolved | campaign_id=%s | campaign_name=%s | match_score=%.3f",
        campaign_id,
        campaign_name,
        match_score,
    )

    # 3. Crwd active (already from get_active_crwds; double-check)
    if crwd.get("status") != "Active" or crwd.get("isDeleted") is True:
        return _fail(out, audit_trail, "Campaign is not active", "campaign_inactive")
    logger.info("run_validation | step=3 | crwd active")

    # 4. Receipt date in campaign window
    date_range = _date_range_from_crwd(crwd)
    purchase_date = state.get("purchase_date")
    ok, err = _validate_date(purchase_date, date_range)
    if not ok:
        logger.info(
            "run_validation | step=4 | date_out_of_range | purchase_date=%s | range=%s",
            purchase_date,
            date_range,
        )
        return _fail(out, audit_trail, err or "Receipt date is outside the campaign period", "receipt_date_outside_period")
    logger.info("run_validation | step=4 | receipt_date_in_window | purchase_date=%s", purchase_date)

    # 5. Proof type (current implementation only accepts order_receipt)
    if crwd.get("type_of_work_proof") != "order_receipt":
        return _fail(out, audit_trail, "This campaign does not accept order receipts", "proof_type_mismatch")
    logger.info("run_validation | step=5 | proof_type=order_receipt")

    # 7. User required
    user_id = state.get("user_id") or ""
    if not user_id:
        return _fail(out, audit_trail, "Missing user", "missing_user")
    logger.info("run_validation | step=7 | user_id=%s", user_id)

    user = get_user(user_id, MONGODB_URI, MONGODB_DATABASE, MONGODB_USERS_COLLECTION)
    if not user:
        return _fail(out, audit_trail, "User not found", "user_not_found")

    # 8. User active
    if user.get("status") != "Active" or user.get("isDeleted") is True:
        return _fail(out, audit_trail, "User is not active or is deleted", "user_not_active")
    logger.info("run_validation | step=8 | user active")

    # 9. User not blocked
    if is_user_blocked(
        user_id,
        MONGODB_URI,
        MONGODB_DATABASE,
        MONGODB_USERS_COLLECTION,
        MONGODB_BLOCK_USERS_COLLECTION,
    ):
        return _fail(out, audit_trail, "User is blocked", "user_blocked")
    logger.info("run_validation | step=9 | user not blocked")

    # 10. User member of this crwd
    if not is_worker_in_campaign(
        user_id,
        campaign_id,
        MONGODB_URI,
        MONGODB_DATABASE,
        MONGODB_ADDED_WORKER_CRWD_MEMBERS_COLLECTION,
    ):
        return _fail(out, audit_trail, "You are not a member of this campaign", "not_campaign_member")
    logger.info("run_validation | step=10 | user is campaign member")

    # 11. Receipt content: campaign rules, merchant/products/vendor/optional order duplicate
    rules = get_campaign_rules(
        campaign_id,
        MONGODB_URI,
        MONGODB_DATABASE,
        MONGODB_CRWDS_COLLECTION,
        MONGODB_CAMPAIGN_RULES_COLLECTION,
    )
    if not rules:
        return _fail(out, audit_trail, "Campaign rules not found", "no_campaign_rules")
    logger.info("run_validation | step=11 | campaign_rules loaded")

    out["campaign_rules"] = rules
    extracted_data: Dict[str, Any] = state.get("extracted_data", {})
    line_items: List[Dict[str, Any]] = state.get("line_items", [])
    vendor_type = state.get("vendor_type", "unknown")
    extraction_confidence = state.get("extraction_confidence") or 0.0

    validation_results: List[Dict[str, Any]] = []
    violations: List[str] = []

    # Merchant validation (optional, based on campaign_rules.valid_merchants)
    valid_merchants = rules.get("valid_merchants", [])
    if valid_merchants:
        ok, err = _validate_merchant(merchant_name, valid_merchants)
        validation_results.append(
            {
                "rule": "merchant_validation",
                "passed": ok,
                "message": err if not ok else "Merchant validated",
                "confidence": 1.0 if ok else 0.0,
            }
        )
        if not ok:
            violations.append(err)
    else:
        validation_results.append(
            {"rule": "merchant_validation", "passed": True, "message": "No merchant restriction", "confidence": 1.0}
        )

    # Store + product validation using gig_stores when available and this is an order_receipt
    gig_stores = rules.get("gig_stores") or []
    matched_store: Optional[Dict[str, Any]] = None
    if gig_stores and state.get("detected_image_type") in (None, "order_receipt"):
        matched_store, store_score = _select_store_for_merchant(gig_stores, merchant_name)
        if not matched_store:
            logger.info(
                "run_validation | store_selection_failed | merchant_name=%s | best_score=%.3f",
                merchant_name,
                store_score,
            )
            return _fail(
                out,
                audit_trail,
                "Could not match this receipt to a configured store for the campaign",
                "store_not_matched",
            )

        out["matched_store_name"] = matched_store.get("store_name")
        out["matched_store_id"] = matched_store.get("store_id")

        ok_store, store_vios, store_score_products, matched_products = _validate_store_products(
            line_items, matched_store.get("products") or []
        )
        if matched_products:
            out["matched_products"] = matched_products

        validation_results.append(
            {
                "rule": "store_product_validation",
                "passed": ok_store,
                "message": "; ".join(store_vios) if not ok_store else "Store products validated",
                "confidence": store_score_products,
            }
        )
        violations.extend(store_vios)
    else:
        # Fallback: legacy product validation using required_products/optional_products
        required = rules.get("required_products", [])
        optional = rules.get("optional_products", [])
        ok, vios, score = _validate_products(line_items, required, optional)
        validation_results.append(
            {
                "rule": "product_validation",
                "passed": ok,
                "message": "; ".join(vios) if not ok else "Products validated",
                "confidence": score,
            }
        )
        violations.extend(vios)

    # Vendor-specific rules
    vendor_rules = rules.get("vendor_specific_rules", {})
    ok, vios = _validate_vendor_rules(extracted_data, vendor_type, vendor_rules)
    validation_results.append(
        {
            "rule": f"{vendor_type}_specific_validation",
            "passed": ok,
            "message": "; ".join(vios) if not ok else f"{vendor_type} rules validated",
            "confidence": 1.0 if ok else 0.0,
        }
    )
    violations.extend(vios)

    # Optional: order number duplicate
    order_number = state.get("order_number") or extracted_data.get("order_number")
    if order_number and order_number_used_in_campaign(
        campaign_id,
        order_number,
        MONGODB_URI,
        MONGODB_DATABASE,
        MONGODB_ORDER_RECEIPT_REVIEWS_COLLECTION,
        exclude_user_id=user_id,
    ):
        violations.append("Order number already used for this campaign")
        validation_results.append(
            {
                "rule": "order_duplicate",
                "passed": False,
                "message": "Order number already used for this campaign",
                "confidence": 0.0,
            }
        )

    # 12. Final decision
    validation_score = _calculate_validation_score(validation_results)
    final_decision, requires_manual_review, review_reason = _determine_final_decision(
        validation_score, violations, extraction_confidence
    )

    logger.info(
        "run_validation | step=12 | final_decision=%s | validation_score=%.2f | violations_count=%s | requires_manual_review=%s | review_reason=%s",
        final_decision,
        validation_score,
        len(violations),
        requires_manual_review,
        review_reason,
    )

    if violations:
        logger.info("run_validation | step=12 | violations=%s", violations[:10])

    if final_decision == "APPROVED":
        validation_status = "verified"
    elif final_decision == "REJECTED":
        validation_status = "rejected"
    else:
        validation_status = "pending_review"

    out["validation_results"] = validation_results
    out["validation_score"] = validation_score
    out["violation_details"] = violations
    out["validation_status"] = validation_status
    out["final_decision"] = final_decision
    out["requires_manual_review"] = requires_manual_review
    out["review_reason"] = review_reason or None
    out["reply_message"] = _build_reply_message(
        final_decision,
        validation_status,
        review_reason or "",
        rules.get("campaign_name") or "",
        validation_score,
        violations,
    )

    audit_trail.append(
        {
            "step": "validation",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "validation_completed",
            "validation_score": validation_score,
            "final_decision": final_decision,
            "violations_count": len(violations),
            "campaign_id": campaign_id,
            "campaign_name": crwd.get("name", ""),
            "status": "success",
        }
    )
    out["audit_trail"] = audit_trail
    return out

