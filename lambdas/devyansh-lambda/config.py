"""
Central configuration from environment variables.
All credentials read from env; TODO comments where secrets must be set in Lambda.
"""

import os
from typing import Optional

# ---------------------------------------------------------------------------
# AWS (Lambda execution role - no placeholders)
# ---------------------------------------------------------------------------
RECEIPTS_BUCKET: str = os.environ.get("RECEIPTS_BUCKET", "")
# TODO: set in Lambda env if using DynamoDB for duplicate detection
HASH_TABLE_NAME: str = os.environ.get("HASH_TABLE_NAME", "")
AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")
# When set (e.g. "true", "1", "yes"), skip only S3 upload in node 1; duplicate hash check (MongoDB) always runs. Image still written to /tmp for extraction.
# Env: BYPASS_S3_UPLOAD or BYPASS_S3_AND_DUPLICATE_CHECK (legacy).
BYPASS_S3_UPLOAD: bool = (
    os.environ.get("BYPASS_S3_UPLOAD", "").lower() in ("true", "1", "yes")
    or os.environ.get("BYPASS_S3_AND_DUPLICATE_CHECK", "").lower() in ("true", "1", "yes")
)
# When set (e.g. "true", "1", "yes"), skip node 3 (validation); set final_decision=PENDING_REVIEW, validation_status=pending_review.
BYPASS_VALIDATION: bool = os.environ.get("BYPASS_VALIDATION", "").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Google Document AI
# TODO: set in Lambda env - GOOGLE_APPLICATION_CREDENTIALS (path to service account JSON)
# TODO: GOOGLE_CLOUD_PROJECT, DOCUMENT_AI_LOCATION, DOCUMENT_AI_PROCESSOR_ID
# ---------------------------------------------------------------------------
GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_CLOUD_PROJECT: Optional[str] = os.environ.get("GOOGLE_CLOUD_PROJECT")
DOCUMENT_AI_LOCATION: str = os.environ.get("DOCUMENT_AI_LOCATION", "us")
DOCUMENT_AI_PROCESSOR_ID: Optional[str] = os.environ.get("DOCUMENT_AI_PROCESSOR_ID")
# Doc AI confidence >= this: use Doc AI result. Below: one VLM call for fraud check + extraction.
DOCUMENT_AI_CONFIDENCE_THRESHOLD: float = float(
    os.environ.get("DOCUMENT_AI_CONFIDENCE_THRESHOLD", "0.8")
)
# When using VLM fallback, minimum receipt_validity_confidence to accept as valid receipt
FRAUD_CHECK_CONFIDENCE_THRESHOLD: float = float(
    os.environ.get("FRAUD_CHECK_CONFIDENCE_THRESHOLD", "0.8")
)

# ---------------------------------------------------------------------------
# AWS Bedrock (VLM fallback)
# Lambda role used; model id from env
# ---------------------------------------------------------------------------
BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
)
BEDROCK_REGION: str = os.environ.get("BEDROCK_REGION", AWS_REGION)

# ---------------------------------------------------------------------------
# MongoDB (CRWD DB on EC2)
# TODO: set in Lambda env - MONGODB_URI for EC2-hosted MongoDB
# ---------------------------------------------------------------------------
MONGODB_URI: Optional[str] = os.environ.get("MONGODB_URI")
MONGODB_DATABASE: str = os.environ.get("MONGODB_DATABASE", "crwd_intelligence")
# Collections: crwds, added_crwd_members; optional campaign_rules if exists
MONGODB_CRWDS_COLLECTION: str = os.environ.get("MONGODB_CRWDS_COLLECTION", "crwds")
MONGODB_ADDED_MEMBERS_COLLECTION: str = os.environ.get(
    "MONGODB_ADDED_MEMBERS_COLLECTION", "added_crwd_members"
)
MONGODB_CAMPAIGN_RULES_COLLECTION: Optional[str] = os.environ.get(
    "MONGODB_CAMPAIGN_RULES_COLLECTION"
)
# Validation: users, block_users, workers, order_receipt_reviews, instructions
MONGODB_USERS_COLLECTION: str = os.environ.get("MONGODB_USERS_COLLECTION", "users")
MONGODB_BLOCK_USERS_COLLECTION: str = os.environ.get(
    "MONGODB_BLOCK_USERS_COLLECTION", "block_users"
)
MONGODB_ADDED_WORKER_CRWD_MEMBERS_COLLECTION: str = os.environ.get(
    "MONGODB_ADDED_WORKER_CRWD_MEMBERS_COLLECTION", "added_worker_crwd_members"
)
MONGODB_ORDER_RECEIPT_REVIEWS_COLLECTION: str = os.environ.get(
    "MONGODB_ORDER_RECEIPT_REVIEWS_COLLECTION", "order_receipt_reviews"
)
MONGODB_INSTRUCTIONS_COLLECTION: str = os.environ.get(
    "MONGODB_INSTRUCTIONS_COLLECTION", "instructions"
)
# Receipt duplicate check: crwdDB.receipt_hash (uses MONGODB_URI)
MONGODB_RECEIPT_HASH_DATABASE: str = os.environ.get("MONGODB_RECEIPT_HASH_DATABASE", "crwdDB")
MONGODB_RECEIPT_HASH_COLLECTION: str = os.environ.get("MONGODB_RECEIPT_HASH_COLLECTION", "receipt_hash")
# Receipt upload history: one record per upload (pass/fail, extracted_data, receipt_type)
MONGODB_RECEIPT_UPLOAD_HISTORY_DATABASE: str = os.environ.get(
    "MONGODB_RECEIPT_UPLOAD_HISTORY_DATABASE", "crwdDB"
)
MONGODB_RECEIPT_UPLOAD_HISTORY_COLLECTION: str = os.environ.get(
    "MONGODB_RECEIPT_UPLOAD_HISTORY_COLLECTION", "receipt_upload_history"
)
# Proof sessions: multi-proof campaigns (user_id + campaign_id + conversation_id)
MONGODB_PROOF_SESSIONS_DATABASE: str = os.environ.get(
    "MONGODB_PROOF_SESSIONS_DATABASE", "crwdDB"
)
MONGODB_PROOF_SESSIONS_COLLECTION: str = os.environ.get(
    "MONGODB_PROOF_SESSIONS_COLLECTION", "proof_sessions"
)

# ---------------------------------------------------------------------------
# Chatwoot (webhook payload: image in attachments[].data_url; reply via API)
# Replace 0.0.0.0 in data_url with CHATWOOT_IMAGE_HOST so Lambda can fetch the image.
# CHATWOOT_BOT_TOKEN: send reply message. CHATWOOT_USER_TOKEN: typing indicator (bots not allowed).
# ---------------------------------------------------------------------------
CHATWOOT_IMAGE_HOST: str = os.environ.get("CHATWOOT_IMAGE_HOST", "44.215.200.55")
CHATWOOT_BASE_URL: str = (os.environ.get("CHATWOOT_BASE_URL", "http://44.215.200.55:3000") or "").rstrip("/")
CHATWOOT_BOT_TOKEN: str = os.environ.get("CHATWOOT_BOT_TOKEN", "XPUkEpb56pFPwWUJVu5JvVKU")
CHATWOOT_USER_TOKEN: str = os.environ.get("CHATWOOT_USER_TOKEN", "MDrsGNERoskafLdnYzVB8KR2")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
