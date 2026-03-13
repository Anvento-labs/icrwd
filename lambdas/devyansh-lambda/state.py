"""
State schema for AI Engine LangGraph workflow.
All values are JSON-serializable (e.g. datetime as ISO string) for Lambda logging.
"""

from typing import TypedDict, Optional, List, Dict, Any


class AIEngineState(TypedDict, total=False):
    """
    State object that flows through the receipt verification workflow.
    Each node can read and update this state. Used by Lambda + LangGraph.
    """
    # Input data
    receipt_image_base64: Optional[str]
    user_id: Optional[str]
    campaign_id: Optional[str]
    submission_timestamp: Optional[str]  # ISO format
    receipt_type: Optional[str]  # order_receipt, order_id, review, selfie
    conversation_id: Optional[str]  # Chatwoot conversation_id for proof_session key

    # Proof session (multi-proof campaigns)
    proof_session_id: Optional[str]
    required_proof_types: List[str]  # e.g. ["order_receipt", "review"]
    submitted_proofs: List[Dict[str, Any]]  # [{proof_type, extracted_data, receipt_s3_key, ...}]
    pending_proof_types: List[str]  # what is still needed
    reply_message: Optional[str]  # set by get_mongo, detect_image, or validation for handler to send

    # Detect node output (image type + fraud + extraction)
    detected_image_type: Optional[str]  # order_receipt | order_id | review | selfie
    is_valid_image: bool
    validity_confidence: Optional[float]
    detection_rejection_reason: Optional[str]

    # Node 1: Input, S3, duplicate check
    receipt_s3_bucket: Optional[str]
    receipt_s3_key: Optional[str]
    image_hash: Optional[str]
    is_duplicate: bool
    receipt_file_path: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    input_validation_status: Optional[str]
    input_validation_errors: List[str]

    # Node 2: Extraction
    extracted_data: Optional[Dict[str, Any]]
    merchant_name: Optional[str]
    purchase_date: Optional[str]  # ISO or YYYY-MM-DD
    order_number: Optional[str]
    total_amount: Optional[float]
    line_items: List[Dict[str, Any]]
    products: List[str]
    phone_number: Optional[str]
    user_name: Optional[str]
    extraction_confidence: Optional[float]
    extraction_errors: List[str]
    vendor_type: Optional[str]

    # Node 3: Validation (campaign_id set from matched crwd; campaign_name for response)
    campaign_name: Optional[str]
    campaign_rules: Optional[Dict[str, Any]]
    validation_results: List[Dict[str, Any]]
    validation_status: Optional[str]
    validation_score: Optional[float]
    violation_details: List[str]
    requires_manual_review: bool
    review_reason: Optional[str]
    final_decision: Optional[str]
    decision_confidence: Optional[float]

    # Bypass flags (from env, set in initial state)
    bypass_validation: Optional[bool]

    # Audit
    audit_trail: List[Dict[str, Any]]
