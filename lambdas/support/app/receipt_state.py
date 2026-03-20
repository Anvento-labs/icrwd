from typing import Any, Dict, List, Optional, TypedDict


class ReceiptGraphState(TypedDict, total=False):
    """
    Receipt proof pipeline state.

    This mirrors the fields used by `devyansh-lambda` Graph 2 (active proof pipeline),
    but only includes keys needed by nodes + validation + Mongo/S3 updates.
    """

    # Input
    receipt_file_path: Optional[str]  # local /tmp path for Bedrock + S3 upload
    image_hash: Optional[str]  # sha256 of the raw image bytes
    user_id: Optional[str]
    campaign_id: Optional[str]
    conversation_id: Optional[str]  # used for proof_session key

    # Duplicate detection stage (get_mongo)
    is_duplicate: bool
    reply_message: Optional[str]  # set when duplicate OR image invalid OR validation requires reply

    # Detection stage (detect_image)
    detected_image_type: Optional[str]  # order_receipt | order_id | review | selfie
    is_valid_image: bool
    validity_confidence: Optional[float]
    detection_rejection_reason: Optional[str]

    # Extraction stage (from Bedrock output)
    extracted_data: Optional[Dict[str, Any]]
    extraction_confidence: Optional[float]

    # Flattened extraction fields used by validation
    merchant_name: Optional[str]
    purchase_date: Optional[str]
    order_number: Optional[str]
    total_amount: Optional[float]
    line_items: List[Dict[str, Any]]

    # Multi-proof stage
    required_proof_types: List[str]
    submitted_proofs: List[Dict[str, Any]]
    pending_proof_types: List[str]

    # Validation outputs
    campaign_name: Optional[str]
    final_decision: Optional[str]  # APPROVED | REJECTED | PENDING_REVIEW
    validation_status: Optional[str]  # verified | rejected | pending_review
    validation_score: Optional[float]
    violation_details: List[str]
    requires_manual_review: bool
    review_reason: Optional[str]
    validation_results: List[Dict[str, Any]]

    # Store match metadata (used by update_mongo -> receipt history)
    matched_store_name: Optional[str]
    matched_store_id: Optional[str]
    matched_products: List[str]

    # S3 + history side effects (update_mongo)
    receipt_s3_bucket: Optional[str]
    receipt_s3_key: Optional[str]
    proof_session_id: Optional[str]

    # Audit (optional; stored in state by validation)
    audit_trail: List[Dict[str, Any]]

