"""
MongoDB client for user campaigns and campaign rules.
TODO: set MONGODB_URI in Lambda env for EC2-hosted MongoDB.
User's campaigns: added_crwd_members (member -> crwd_id) + crwds.
Campaign rules: derived from crwds (start_date, end_date, type_of_work_proof);
  optional campaign_rules collection keyed by crwd_id for valid_merchants, required_products.
Campaign discovery: match receipt merchant_name to crwds.name (fuzzy).
"""

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_pymongo = None
_client = None


def _get_pymongo():
    global _pymongo
    if _pymongo is None:
        try:
            from pymongo import MongoClient
            _pymongo = MongoClient
        except ImportError:
            logger.warning("pymongo not available")
            return None
    return _pymongo


def get_client(uri: str):
    """Get or create MongoDB client (reuse for Lambda)."""
    global _client
    if _client is None and uri:
        MongoClient = _get_pymongo()
        if MongoClient:
            _client = MongoClient(uri)
    return _client


def _normalize_name(s: str) -> str:
    """Normalize for fuzzy match: lowercase, strip, collapse spaces."""
    if not s:
        return ""
    return " ".join(str(s).lower().strip().split())


def get_active_crwds(
    uri: str,
    database: str,
    crwds_collection: str,
) -> List[Dict[str, Any]]:
    """
    Fetch all active crwds (status Active, isDeleted false).
    Used for matching receipt merchant_name to crwd name.
    """
    client = get_client(uri)
    if not client:
        logger.warning("get_active_crwds | client=None | database=%s", database)
        return []

    db = client[database]
    coll = db[crwds_collection]
    cursor = coll.find(
        {"status": "Active", "isDeleted": False},
        {"_id": 1, "name": 1, "start_date": 1, "end_date": 1, "type_of_work_proof": 1, "status": 1, "isDeleted": 1},
    )
    crwds = list(cursor)
    logger.info("get_active_crwds | database=%s | collection=%s | count=%s", database, crwds_collection, len(crwds))
    return crwds


def find_crwd_by_merchant_name(
    uri: str,
    database: str,
    crwds_collection: str,
    merchant_name: str,
    min_similarity: float = 0.7,
) -> Tuple[Optional[Dict[str, Any]], float]:
    """
    Find best-matching crwd by fuzzy-matching merchant_name to crwds.name.
    Returns (crwd_doc, score); (None, 0) if no match >= min_similarity.
    """
    if not (merchant_name and (merchant_name or "").strip()):
        return None, 0.0

    crwds = get_active_crwds(uri, database, crwds_collection)
    if not crwds:
        return None, 0.0

    norm_merchant = _normalize_name(merchant_name)
    best_crwd = None
    best_score = 0.0

    for crwd in crwds:
        crwd_name = crwd.get("name") or ""
        norm_crwd = _normalize_name(crwd_name)
        if not norm_crwd:
            continue
        ratio = SequenceMatcher(None, norm_merchant, norm_crwd).ratio()
        # Also allow substring: merchant contains crwd name or vice versa
        if norm_crwd in norm_merchant or norm_merchant in norm_crwd:
            ratio = max(ratio, 0.85)
        if ratio > best_score:
            best_score = ratio
            best_crwd = crwd

    if best_score >= min_similarity and best_crwd:
        logger.info(
            "find_crwd_by_merchant_name | merchant_name=%s | matched_crwd=%s | campaign_id=%s | score=%.3f",
            merchant_name,
            best_crwd.get("name"),
            str(best_crwd.get("_id", "")),
            best_score,
        )
        return best_crwd, best_score
    logger.info(
        "find_crwd_by_merchant_name | merchant_name=%s | result=no_match | best_score=%.3f | min_similarity=%.2f",
        merchant_name,
        best_score,
        min_similarity,
    )
    return None, best_score


def get_campaigns_for_user(
    user_id: str,
    uri: str,
    database: str,
    added_members_collection: str,
    crwds_collection: str,
) -> List[Dict[str, Any]]:
    """
    Fetch campaigns the user is a member of.

    Queries added_crwd_members where member = user_id (ObjectId or string),
    then loads crwds documents for those crwd_id values.
    Filters: status = 'Active', isDeleted = False.

    Args:
        user_id: User ID (string; will be converted to ObjectId if valid 24-char hex)
        uri: MongoDB connection string
        database: Database name
        added_members_collection: e.g. added_crwd_members
        crwds_collection: e.g. crwds

    Returns:
        List of campaign (crwd) documents with _id, start_date, end_date, name, etc.
    """
    client = get_client(uri)
    if not client:
        logger.warning("MongoDB client not available; MONGODB_URI not set?")
        return []

    db = client[database]
    members_coll = db[added_members_collection]
    crwds_coll = db[crwds_collection]

    try:
        from bson import ObjectId
        member_query = {"member": ObjectId(user_id) if _is_object_id(user_id) else user_id}
    except Exception:
        member_query = {"member": user_id}

    member_query["status"] = "Active"
    member_query["isDeleted"] = False

    cursor = members_coll.find(member_query, {"crwd_id": 1})
    crwd_ids = [doc["crwd_id"] for doc in cursor if doc.get("crwd_id")]

    if not crwd_ids:
        return []

    try:
        from bson import ObjectId
        ids = [ObjectId(x) if isinstance(x, str) and _is_object_id(x) else x for x in crwd_ids]
    except Exception:
        ids = crwd_ids

    campaigns = list(
        crwds_coll.find(
            {"_id": {"$in": ids}, "status": "Active", "isDeleted": False}
        )
    )
    return campaigns


def get_campaign_rules(
    campaign_id: str,
    uri: str,
    database: str,
    crwds_collection: str,
    campaign_rules_collection: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get validation rules for a campaign.

    If campaign_rules_collection is set, look up document by campaign_id/crw_id.
    Otherwise derive from crwds: date_range from start_date/end_date,
    type_of_work_proof. valid_merchants and required_products left empty
    unless present in campaign_rules collection.
    TODO: Enrich from instructions collection if needed.

    Args:
        campaign_id: Campaign (crwd) ID
        uri: MongoDB connection string
        database: Database name
        crwds_collection: e.g. crwds
        campaign_rules_collection: Optional collection for full rules

    Returns:
        Dict with campaign_id, campaign_name, valid_merchants, date_range,
        required_products, optional_products, vendor_specific_rules; or None
    """
    client = get_client(uri)
    if not client:
        return None

    db = client[database]
    crwds_coll = db[crwds_collection]

    try:
        from bson import ObjectId
        cid = ObjectId(campaign_id) if _is_object_id(campaign_id) else campaign_id
    except Exception:
        cid = campaign_id

    crwd = crwds_coll.find_one({"_id": cid, "status": "Active", "isDeleted": False})
    if not crwd:
        logger.info("get_campaign_rules | campaign_id=%s | crwd_not_found", campaign_id)
        return None

    # Derive date range from crwds
    start_date = crwd.get("start_date")
    end_date = crwd.get("end_date")
    if hasattr(start_date, "strftime"):
        start_date = start_date.strftime("%Y-%m-%d")
    if hasattr(end_date, "strftime"):
        end_date = end_date.strftime("%Y-%m-%d")
    date_range = {}
    if start_date:
        date_range["start_date"] = start_date
    if end_date:
        date_range["end_date"] = end_date
    if not date_range:
        date_range = {"start_date": "1970-01-01", "end_date": "2099-12-31"}

    rules = {
        "campaign_id": str(crwd["_id"]),
        "campaign_name": crwd.get("name", ""),
        "valid_merchants": [],
        "date_range": date_range,
        "required_products": [],
        "optional_products": [],
        "vendor_specific_rules": {},
        "required_proof_types": [],
    }
    # required_proof_types: from campaign_rules extra, else derive from crwd.type_of_work_proof
    single_proof = crwd.get("type_of_work_proof")
    if single_proof and isinstance(single_proof, str):
        rules["required_proof_types"] = [single_proof.strip()]

    if campaign_rules_collection:
        rules_coll = db[campaign_rules_collection]
        extra = rules_coll.find_one({"campaign_id": campaign_id}) or rules_coll.find_one(
            {"crwd_id": cid}
        )
        if extra:
            rules["valid_merchants"] = extra.get("valid_merchants", [])
            rules["required_products"] = extra.get("required_products", [])
            rules["optional_products"] = extra.get("optional_products", [])
            rules["vendor_specific_rules"] = extra.get("vendor_specific_rules", {})
            if extra.get("date_range"):
                rules["date_range"] = extra["date_range"]
            if extra.get("required_proof_types"):
                rules["required_proof_types"] = list(extra["required_proof_types"])

    logger.info(
        "get_campaign_rules | campaign_id=%s | campaign_name=%s | valid_merchants=%s | required_products=%s | required_proof_types=%s",
        campaign_id,
        rules.get("campaign_name", ""),
        len(rules.get("valid_merchants", [])),
        len(rules.get("required_products", [])),
        rules.get("required_proof_types", []),
    )
    return rules


def _is_object_id(s: str) -> bool:
    """Check if string is 24-char hex (ObjectId)."""
    if not isinstance(s, str) or len(s) != 24:
        return False
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


def _to_object_id(val: Any) -> Any:
    """Convert string to ObjectId if valid 24-char hex; else return as-is."""
    try:
        from bson import ObjectId
        if isinstance(val, str) and _is_object_id(val):
            return ObjectId(val)
    except Exception:
        pass
    return val


def get_user(
    user_id: str,
    uri: str,
    database: str,
    users_collection: str,
) -> Optional[Dict[str, Any]]:
    """Fetch user by _id. Returns user doc or None."""
    client = get_client(uri)
    if not client or not user_id:
        if not user_id:
            logger.debug("get_user | user_id=empty")
        return None
    db = client[database]
    coll = db[users_collection]
    oid = _to_object_id(user_id)
    user = coll.find_one({"_id": oid})
    logger.info("get_user | user_id=%s | found=%s", user_id, user is not None)
    return user


def is_user_blocked(
    user_id: str,
    uri: str,
    database: str,
    users_collection: str,
    block_users_collection: str,
    room_id: Optional[str] = None,
) -> bool:
    """Return True if user is blocked (users.isBlocked or in block_users)."""
    user = get_user(user_id, uri, database, users_collection)
    if user and user.get("isBlocked") is True:
        logger.info("is_user_blocked | user_id=%s | blocked=True (user.isBlocked)", user_id)
        return True
    client = get_client(uri)
    if not client:
        return False
    db = client[database]
    block_coll = db[block_users_collection]
    query = {
        "blocked_users_id": _to_object_id(user_id),
        "isBlocked": True,
        "status": "Active",
        "isDeleted": False,
    }
    if room_id:
        query["room_id"] = _to_object_id(room_id)
    blocked = block_coll.find_one(query) is not None
    logger.info("is_user_blocked | user_id=%s | blocked=%s", user_id, blocked)
    return blocked


def is_worker_in_campaign(
    user_id: str,
    campaign_id: str,
    uri: str,
    database: str,
    added_worker_crwd_members_collection: str,
) -> bool:
    """Return True if user is an active, accepted worker/member of this campaign."""
    client = get_client(uri)
    if not client or not user_id or not campaign_id:
        return False
    db = client[database]
    coll = db[added_worker_crwd_members_collection]
    uid = _to_object_id(user_id)
    cid = _to_object_id(campaign_id)
    doc = coll.find_one({
        "crwd_id": cid,
        "$or": [{"member": uid}, {"worker_id": uid}],
        "status": "Active",
        "isDeleted": False,
        "isAccept": True,
    })
    in_campaign = doc is not None
    logger.info("is_worker_in_campaign | user_id=%s | campaign_id=%s | in_campaign=%s", user_id, campaign_id, in_campaign)
    return in_campaign


def get_campaign_by_id(
    campaign_id: str,
    uri: str,
    database: str,
    crwds_collection: str,
) -> Optional[Dict[str, Any]]:
    """Fetch single active crwd by _id. Returns crwd doc or None."""
    client = get_client(uri)
    if not client or not campaign_id:
        return None
    db = client[database]
    coll = db[crwds_collection]
    cid = _to_object_id(campaign_id)
    crwd = coll.find_one({"_id": cid, "status": "Active", "isDeleted": False})
    logger.info("get_campaign_by_id | campaign_id=%s | found=%s", campaign_id, crwd is not None)
    return crwd


def order_number_used_in_campaign(
    campaign_id: str,
    order_number: str,
    uri: str,
    database: str,
    order_receipt_reviews_collection: str,
    exclude_user_id: Optional[str] = None,
) -> bool:
    """
    Return True if this order_number is already used in this campaign by another user.
    If exclude_user_id is set, ignore submissions by that user (same-user resubmit).
    """
    order_str = str(order_number).strip() if order_number else ""
    if not order_str:
        return False
    client = get_client(uri)
    if not client:
        return False
    db = client[database]
    coll = db[order_receipt_reviews_collection]
    cid = _to_object_id(campaign_id)
    query = {
        "crwd_id": cid,
        "order_number": order_str,
        "status": "Active",
        "isDeleted": False,
    }
    if exclude_user_id:
        query["order_generated_by"] = {"$ne": _to_object_id(exclude_user_id)}
    used = coll.find_one(query) is not None
    logger.info(
        "order_number_used_in_campaign | campaign_id=%s | order_number=%s | exclude_user_id=%s | already_used=%s",
        campaign_id,
        order_str[:20] + "..." if len(order_str) > 20 else order_str,
        exclude_user_id,
        used,
    )
    return used


# ---------------------------------------------------------------------------
# Receipt hash (duplicate detection) - crwdDB.receipt_hash
# ---------------------------------------------------------------------------


def receipt_hash_exists(
    uri: str,
    database: str,
    receipt_hash_collection: str,
    image_hash: str,
) -> bool:
    """
    Return True if this image_hash already exists in receipt_hash collection (duplicate receipt).
    """
    if not image_hash or not (image_hash or "").strip():
        return False
    client = get_client(uri)
    if not client:
        logger.warning("receipt_hash_exists | client=None")
        return False
    db = client[database]
    coll = db[receipt_hash_collection]
    doc = coll.find_one({"image_hash": image_hash.strip()})
    exists = doc is not None
    logger.info(
        "receipt_hash_exists | database=%s | collection=%s | image_hash_prefix=%s | exists=%s",
        database,
        receipt_hash_collection,
        (image_hash[:16] + "...") if len(image_hash) > 16 else image_hash,
        exists,
    )
    return exists


def receipt_hash_insert(
    uri: str,
    database: str,
    receipt_hash_collection: str,
    image_hash: str,
    user_id: Optional[str] = None,
    s3_object_key: Optional[str] = None,
    status: str = "active",
) -> None:
    """
    Insert a new receipt_hash document after successful S3 upload.
    Fields: image_hash, user_id, s3_object_key, upload_timestamp, status.
    """
    from datetime import datetime
    if not image_hash or not (image_hash or "").strip():
        return
    client = get_client(uri)
    if not client:
        logger.warning("receipt_hash_insert | client=None")
        return
    db = client[database]
    coll = db[receipt_hash_collection]
    doc = {
        "image_hash": image_hash.strip(),
        "user_id": user_id,
        "s3_object_key": s3_object_key,
        "upload_timestamp": datetime.utcnow(),
        "status": status,
    }
    coll.insert_one(doc)
    logger.info(
        "receipt_hash_insert | database=%s | collection=%s | image_hash_prefix=%s | user_id=%s",
        database,
        receipt_hash_collection,
        (image_hash[:16] + "...") if len(image_hash) > 16 else image_hash,
        user_id,
    )


# ---------------------------------------------------------------------------
# Receipt upload history - crwdDB.receipt_upload_history
# ---------------------------------------------------------------------------


def receipt_upload_history_insert(
    uri: str,
    database: str,
    collection: str,
    *,
    user_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    receipt_s3_key: Optional[str] = None,
    status: str,
    fail_reason: Optional[str] = None,
    extracted_data: Optional[Dict[str, Any]] = None,
    receipt_type: str = "order_receipt",
    request_id: Optional[str] = None,
) -> None:
    """
    Insert one record per receipt upload. S3 key (receipt_s3_key) matches the object
    name in S3 and the key stored in receipt_hash for easy lookup.
    """
    from datetime import datetime
    if not uri or not database or not collection:
        return
    client = get_client(uri)
    if not client:
        logger.warning("receipt_upload_history_insert | client=None")
        return
    db = client[database]
    coll = db[collection]
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "campaign_id": campaign_id,
        "receipt_s3_key": receipt_s3_key,
        "status": status,
        "fail_reason": fail_reason,
        "extracted_data": extracted_data,
        "receipt_type": receipt_type,
        "created_at": now,
        "updated_at": now,
    }
    if request_id:
        doc["request_id"] = request_id
    coll.insert_one(doc)
    logger.info(
        "receipt_upload_history_insert | database=%s | collection=%s | user_id=%s | status=%s | receipt_s3_key=%s",
        database,
        collection,
        user_id,
        status,
        receipt_s3_key,
    )


# ---------------------------------------------------------------------------
# Proof sessions (multi-proof campaigns)
# ---------------------------------------------------------------------------

def _proof_session_id(user_id: str, campaign_id: str, conversation_id: Optional[str] = None) -> str:
    """Stable session key: user_id + campaign_id + conversation_id or 'api'."""
    conv = (conversation_id or "").strip() or "api"
    return f"{user_id}|{campaign_id}|{conv}"


def proof_session_get(
    uri: str,
    database: str,
    collection: str,
    user_id: str,
    campaign_id: str,
    conversation_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get existing proof session by user_id, campaign_id, conversation_id.
    Returns document with session_id, required_proof_types, submitted_proofs, etc., or None.
    """
    if not uri or not database or not collection or not user_id or not campaign_id:
        return None
    client = get_client(uri)
    if not client:
        logger.warning("[get_mongo] proof_session_get | client=None")
        return None
    db = client[database]
    coll = db[collection]
    sid = _proof_session_id(user_id, campaign_id, conversation_id)
    doc = coll.find_one({"session_id": sid})
    if doc:
        # Convert any ObjectId/datetime for JSON-serializable state
        submitted = doc.get("submitted_proofs") or []
        out = {
            "session_id": sid,
            "user_id": doc.get("user_id"),
            "campaign_id": doc.get("campaign_id"),
            "conversation_id": doc.get("conversation_id"),
            "required_proof_types": list(doc.get("required_proof_types") or []),
            "submitted_proofs": submitted,
        }
        logger.info(
            "[get_mongo] proof_session_get | session_id=%s | submitted_count=%s | required=%s",
            sid,
            len(submitted),
            out.get("required_proof_types"),
        )
        return out
    logger.info("[get_mongo] proof_session_get | session_id=%s | not_found", sid)
    return None


def proof_session_upsert(
    uri: str,
    database: str,
    collection: str,
    user_id: str,
    campaign_id: str,
    required_proof_types: List[str],
    submitted_proofs: List[Dict[str, Any]],
    conversation_id: Optional[str] = None,
) -> str:
    """
    Create or update proof session. submitted_proofs is the full list (append new proof in caller).
    Returns session_id.
    """
    from datetime import datetime
    if not uri or not database or not collection or not user_id or not campaign_id:
        return ""
    client = get_client(uri)
    if not client:
        logger.warning("[update_mongo] proof_session_upsert | client=None")
        return ""
    db = client[database]
    coll = db[collection]
    sid = _proof_session_id(user_id, campaign_id, conversation_id)
    now = datetime.utcnow()
    doc = {
        "session_id": sid,
        "user_id": user_id,
        "campaign_id": campaign_id,
        "conversation_id": conversation_id,
        "required_proof_types": required_proof_types,
        "submitted_proofs": submitted_proofs,
        "updated_at": now,
    }
    coll.update_one(
        {"session_id": sid},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    logger.info(
        "[update_mongo] proof_session_upsert | session_id=%s | submitted_count=%s",
        sid,
        len(submitted_proofs),
    )
    return sid


def proof_session_delete(
    uri: str,
    database: str,
    collection: str,
    session_id: str,
) -> bool:
    """Remove proof session (e.g. after all proofs submitted and validation done)."""
    if not uri or not database or not collection or not session_id:
        return False
    client = get_client(uri)
    if not client:
        return False
    db = client[database]
    coll = db[collection]
    result = coll.delete_one({"session_id": session_id})
    deleted = result.deleted_count > 0
    logger.info("[update_mongo] proof_session_delete | session_id=%s | deleted=%s", session_id, deleted)
    return deleted
