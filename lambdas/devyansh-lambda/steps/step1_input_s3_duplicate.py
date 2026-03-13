"""
Step 1: Input, duplicate check by image hash, optional S3 upload.
Decode/validate image -> compute hash -> always check duplicate (MongoDB receipt_hash or DynamoDB) -> if not duplicate, upload to S3 (or skip if BYPASS_S3_UPLOAD) -> set local path for Step 2.
"""

import base64
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict

from state import AIEngineState
from config import (
    RECEIPTS_BUCKET,
    HASH_TABLE_NAME,
    AWS_REGION,
    BYPASS_S3_UPLOAD,
    MONGODB_URI,
    MONGODB_RECEIPT_HASH_DATABASE,
    MONGODB_RECEIPT_HASH_COLLECTION,
)
from services.s3 import upload_receipt
from services.duplicate_check import compute_image_hash, check_duplicate
from services.mongodb_campaigns import receipt_hash_exists, receipt_hash_insert

logger = logging.getLogger(__name__)

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _decode_base64_image(base64_data: str) -> bytes:
    """Decode base64 image; strip data URL prefix if present."""
    if "," in base64_data:
        base64_data = base64_data.split(",", 1)[1]
    return base64.b64decode(base64_data)


def _validate_image_bytes(data: bytes) -> tuple[bool, str, str]:
    """Validate image magic bytes. Returns (is_valid, file_type, error_message)."""
    if len(data) < 12:
        return False, "unknown", "Image data too short"
    if data[:3] == JPEG_MAGIC:
        return True, "image", ""
    if data[:8] == PNG_MAGIC:
        return True, "image", ""
    return False, "unknown", "Unsupported image format (expected JPEG or PNG)"


def run_input_s3_duplicate(state: AIEngineState) -> AIEngineState:
    """
    Step 1: Receipt input, duplicate check (always), optional S3 upload.

    - Decode receipt_image_base64; validate image
    - Compute SHA-256 hash; always check duplicate (MongoDB receipt_hash or DynamoDB)
    - If duplicate: set is_duplicate=True and return
    - Else: if BYPASS_S3_UPLOAD skip S3 and write to /tmp only; else upload to S3 and write to /tmp
    - Set receipt_file_path for Step 2
    """
    logger.info("Step input_s3_duplicate: started")
    audit_trail = list(state.get("audit_trail", []))
    errors = list(state.get("input_validation_errors", []))
    out: Dict[str, Any] = {
        **state,
        "input_validation_status": "invalid",
        "input_validation_errors": errors,
        "is_duplicate": False,
        "audit_trail": audit_trail,
    }

    base64_img = state.get("receipt_image_base64")
    if not base64_img:
        errors.append("No receipt image provided (receipt_image_base64)")
        audit_trail.append({
            "step": "input_s3_duplicate",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "validation_failed",
            "reason": "missing_image",
            "status": "error",
        })
        return out

    try:
        image_bytes = _decode_base64_image(base64_img)
        logger.info("Step input_s3_duplicate: image decoded | size_bytes=%s", len(image_bytes))
    except Exception as e:
        logger.warning("Step input_s3_duplicate: decode failed | error=%s", e)
        errors.append(f"Failed to decode base64 image: {e}")
        audit_trail.append({
            "step": "input_s3_duplicate",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "decode_failed",
            "error": str(e),
            "status": "error",
        })
        return out

    is_valid, file_type, validation_error = _validate_image_bytes(image_bytes)
    logger.info("Step input_s3_duplicate: image validated | is_valid=%s | file_type=%s", is_valid, file_type)
    if not is_valid:
        logger.warning("Step input_s3_duplicate: validation failed | reason=%s", validation_error)
        errors.append(validation_error)
        audit_trail.append({
            "step": "input_s3_duplicate",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "validation_failed",
            "reason": validation_error,
            "status": "error",
        })
        return out

    image_hash = compute_image_hash(image_bytes)
    out["image_hash"] = image_hash
    out["file_type"] = file_type
    out["file_size"] = len(image_bytes)

    # Duplicate hash check: always run (MongoDB receipt_hash when MONGODB_URI set, else DynamoDB fallback)
    logger.info("Step input_s3_duplicate: duplicate hash check start | image_hash_prefix=%s", image_hash[:16])
    is_dup = False
    duplicate_check_source = "none"
    if MONGODB_URI:
        logger.info("Step input_s3_duplicate: duplicate check (MongoDB) | db=%s | collection=%s", MONGODB_RECEIPT_HASH_DATABASE, MONGODB_RECEIPT_HASH_COLLECTION)
        is_dup = receipt_hash_exists(MONGODB_URI, MONGODB_RECEIPT_HASH_DATABASE, MONGODB_RECEIPT_HASH_COLLECTION, image_hash)
        duplicate_check_source = "MongoDB"
    if not is_dup and HASH_TABLE_NAME:
        logger.info("Step input_s3_duplicate: duplicate check (DynamoDB) | HASH_TABLE_NAME=%s", HASH_TABLE_NAME)
        is_dup, _ = check_duplicate(image_hash, HASH_TABLE_NAME, AWS_REGION)
        if duplicate_check_source == "none":
            duplicate_check_source = "DynamoDB"
    if not MONGODB_URI and not HASH_TABLE_NAME:
        logger.info("Step input_s3_duplicate: duplicate check skipped | MONGODB_URI and HASH_TABLE_NAME not set")
    logger.info("Step input_s3_duplicate: duplicate hash check done | is_duplicate=%s | source=%s", is_dup, duplicate_check_source)
    if is_dup:
        out["is_duplicate"] = True
        out["input_validation_status"] = "valid"
        out["input_validation_errors"] = []
        out["review_reason"] = "Duplicate receipt: this image has already been submitted."
        out["final_decision"] = "REJECTED"
        out["validation_status"] = "rejected"
        audit_trail.append({
            "step": "input_s3_duplicate",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "duplicate_detected",
            "image_hash": image_hash[:16] + "...",
            "reason": "Duplicate receipt: this image has already been submitted.",
            "status": "duplicate",
        })
        out["audit_trail"] = audit_trail
        return out

    # Bypass only S3 upload: write to /tmp, store hash in MongoDB if configured, then continue to extraction
    if BYPASS_S3_UPLOAD:
        logger.info("Step input_s3_duplicate: BYPASS_S3_UPLOAD=true | skipping S3 upload, writing to /tmp only")
        tmp_dir = "/tmp/receipts"
        os.makedirs(tmp_dir, exist_ok=True)
        ext = "jpg" if "jpeg" in file_type or file_type == "image" else "png"
        local_path = os.path.join(tmp_dir, f"receipt_{uuid.uuid4().hex[:12]}.{ext}")
        with open(local_path, "wb") as f:
            f.write(image_bytes)
        out["receipt_file_path"] = local_path
        out["input_validation_status"] = "valid"
        out["input_validation_errors"] = []
        out["receipt_s3_bucket"] = None
        out["receipt_s3_key"] = None
        if MONGODB_URI:
            try:
                user_id = state.get("user_id") or "anonymous"
                receipt_hash_insert(
                    MONGODB_URI,
                    MONGODB_RECEIPT_HASH_DATABASE,
                    MONGODB_RECEIPT_HASH_COLLECTION,
                    image_hash,
                    user_id=user_id,
                    s3_object_key=None,
                    status="active",
                )
            except Exception as e:
                logger.warning("Step input_s3_duplicate: receipt_hash_insert failed (non-fatal) | error=%s", e)
        audit_trail.append({
            "step": "input_s3_duplicate",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "stored_bypass",
            "reason": "BYPASS_S3_UPLOAD",
            "local_path": local_path,
            "status": "success",
        })
        out["audit_trail"] = audit_trail
        return out

    if not RECEIPTS_BUCKET:
        logger.warning("Step input_s3_duplicate: RECEIPTS_BUCKET not set | skipping S3 upload, routing to END")
        errors.append("RECEIPTS_BUCKET not set")
        audit_trail.append({
            "step": "input_s3_duplicate",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "upload_skipped",
            "reason": "bucket_not_configured",
            "status": "error",
        })
        return out

    user_id = state.get("user_id") or "anonymous"
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ext = "jpg" if "jpeg" in file_type or file_type == "image" else "png"
    key = f"receipts/{user_id}/{ts}_{uuid.uuid4().hex[:8]}.{ext}"
    content_type = "image/jpeg" if ext == "jpg" else "image/png"

    logger.info("Step input_s3_duplicate: uploading to S3 | bucket=%s | key=%s", RECEIPTS_BUCKET, key)
    try:
        upload_receipt(
            bucket=RECEIPTS_BUCKET,
            key=key,
            body=image_bytes,
            content_type=content_type,
            metadata={"image_hash": image_hash},
            region=AWS_REGION,
        )
    except Exception as e:
        logger.warning("Step input_s3_duplicate: S3 upload failed | error=%s", e)
        errors.append(f"S3 upload failed: {e}")
        audit_trail.append({
            "step": "input_s3_duplicate",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "upload_failed",
            "error": str(e),
            "status": "error",
        })
        return out

    out["receipt_s3_bucket"] = RECEIPTS_BUCKET
    out["receipt_s3_key"] = key

    # Store hash in MongoDB receipt_hash (crwdDB.receipt_hash) for future duplicate checks
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
            logger.warning("Step input_s3_duplicate: receipt_hash_insert failed (non-fatal) | error=%s", e)

    tmp_dir = "/tmp/receipts"
    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, os.path.basename(key))
    with open(local_path, "wb") as f:
        f.write(image_bytes)
    out["receipt_file_path"] = local_path
    out["input_validation_status"] = "valid"
    out["input_validation_errors"] = []
    logger.info("Step input_s3_duplicate: success | receipt_s3_bucket=%s | receipt_s3_key=%s | input_validation_status=valid", RECEIPTS_BUCKET, key)
    audit_trail.append({
        "step": "input_s3_duplicate",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "stored",
        "s3_key": key,
        "image_hash_prefix": image_hash[:16] + "...",
        "status": "success",
    })
    out["audit_trail"] = audit_trail
    return out
