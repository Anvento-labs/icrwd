"""
Node: Update MongoDB (writes only). S3 upload, receipt_hash, receipt_upload_history, proof_session.
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict

from state import AIEngineState
from config import (
    MONGODB_URI,
    RECEIPTS_BUCKET,
    AWS_REGION,
    BYPASS_S3_UPLOAD,
    MONGODB_RECEIPT_HASH_DATABASE,
    MONGODB_RECEIPT_HASH_COLLECTION,
    MONGODB_RECEIPT_UPLOAD_HISTORY_DATABASE,
    MONGODB_RECEIPT_UPLOAD_HISTORY_COLLECTION,
    MONGODB_PROOF_SESSIONS_DATABASE,
    MONGODB_PROOF_SESSIONS_COLLECTION,
)
from services.mongodb_campaigns import (
    receipt_hash_insert,
    receipt_upload_history_insert,
    proof_session_upsert,
    proof_session_delete,
)
from services.s3 import upload_receipt

logger = logging.getLogger(__name__)


def node_update_mongo(state: AIEngineState) -> Dict[str, Any]:
    """
    LangGraph node: all MongoDB writes. S3 upload (if not duplicate, not bypass),
    receipt_hash insert, receipt_upload_history insert, proof_session upsert/delete.
    """
    logger.info("[update_mongo] Node called | is_duplicate=%s | receipt_file_path=%s", state.get("is_duplicate"), state.get("receipt_file_path"))
    out: Dict[str, Any] = {}

    user_id = state.get("user_id") or "anonymous"
    campaign_id = state.get("campaign_id") or ""
    image_hash = state.get("image_hash")
    is_duplicate = state.get("is_duplicate", False)
    receipt_file_path = state.get("receipt_file_path")
    conversation_id = state.get("conversation_id")

    # 1. S3 upload + receipt_hash (when not duplicate and not bypass)
    if not is_duplicate and receipt_file_path and RECEIPTS_BUCKET and not BYPASS_S3_UPLOAD and image_hash:
        try:
            with open(receipt_file_path, "rb") as f:
                image_bytes = f.read()
            ext = "jpg" if receipt_file_path.lower().endswith((".jpg", ".jpeg")) else "png"
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"receipts/{user_id}/{ts}_{uuid.uuid4().hex[:8]}.{ext}"
            content_type = "image/jpeg" if ext == "jpg" else "image/png"
            upload_receipt(
                bucket=RECEIPTS_BUCKET,
                key=key,
                body=image_bytes,
                content_type=content_type,
                metadata={"image_hash": image_hash},
                region=AWS_REGION,
            )
            out["receipt_s3_bucket"] = RECEIPTS_BUCKET
            out["receipt_s3_key"] = key
            if MONGODB_URI:
                try:
                    receipt_hash_insert(
                        MONGODB_URI,
                        MONGODB_RECEIPT_HASH_DATABASE,
                        MONGODB_RECEIPT_HASH_COLLECTION,
                        image_hash,
                        user_id=user_id,
                        s3_object_key=key,
                        status="active",
                    )
                except Exception as e:
                    logger.warning("[update_mongo] receipt_hash_insert failed (non-fatal) | error=%s", e)
        except Exception as e:
            logger.warning("[update_mongo] S3 upload failed | error=%s", e)

    receipt_s3_key = out.get("receipt_s3_key") or state.get("receipt_s3_key")

    # 2. receipt_upload_history
    if MONGODB_URI:
        try:
            status = "pass" if state.get("final_decision") == "APPROVED" else "fail"
            fail_reason = state.get("review_reason") or state.get("reply_message")
            extracted_data = state.get("extracted_data")
            if not extracted_data and (state.get("merchant_name") or state.get("purchase_date")):
                extracted_data = {
                    "merchant_name": state.get("merchant_name"),
                    "purchase_date": state.get("purchase_date"),
                    "order_number": state.get("order_number"),
                    "total_amount": state.get("total_amount"),
                    "extraction_confidence": state.get("extraction_confidence"),
                }
            receipt_upload_history_insert(
                MONGODB_URI,
                MONGODB_RECEIPT_UPLOAD_HISTORY_DATABASE,
                MONGODB_RECEIPT_UPLOAD_HISTORY_COLLECTION,
                user_id=user_id,
                campaign_id=campaign_id or None,
                receipt_s3_key=receipt_s3_key,
                status=status,
                fail_reason=fail_reason,
                extracted_data=extracted_data,
                receipt_type="order_receipt",
            )
        except Exception as e:
            logger.warning("[update_mongo] receipt_upload_history_insert failed (non-fatal) | error=%s", e)

    # 3. proof_session upsert (when validation set pending_proof_types and we have submitted_proofs to save)
    required = state.get("required_proof_types") or []
    submitted = state.get("submitted_proofs") or []
    pending = state.get("pending_proof_types") or []
    if MONGODB_URI and user_id and campaign_id and required:
        if pending:
            try:
                sid = proof_session_upsert(
                    MONGODB_URI,
                    MONGODB_PROOF_SESSIONS_DATABASE,
                    MONGODB_PROOF_SESSIONS_COLLECTION,
                    user_id=user_id,
                    campaign_id=campaign_id,
                    required_proof_types=required,
                    submitted_proofs=submitted,
                    conversation_id=conversation_id,
                )
                out["proof_session_id"] = sid
            except Exception as e:
                logger.warning("[update_mongo] proof_session_upsert failed (non-fatal) | error=%s", e)
        elif state.get("final_decision") in ("APPROVED", "REJECTED") and state.get("proof_session_id"):
            try:
                proof_session_delete(
                    MONGODB_URI,
                    MONGODB_PROOF_SESSIONS_DATABASE,
                    MONGODB_PROOF_SESSIONS_COLLECTION,
                    state["proof_session_id"],
                )
            except Exception as e:
                logger.warning("[update_mongo] proof_session_delete failed (non-fatal) | error=%s", e)

    logger.info(
        "[update_mongo] Node done | receipt_s3_key=%s | history_inserted | session_updated=%s",
        receipt_s3_key,
        bool(pending and required),
    )
    return out
