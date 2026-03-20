"""
Receipt proof pipeline configuration for the `support` lambda.

This ports the relevant environment variable mapping from
`lambdas/devyansh-lambda/config.py`, but only includes what the active
proof pipeline needs (no Document AI, and no BYPASS_VALIDATION).
"""

import os
from typing import Optional

# ---------------------------------------------------------------------------
# AWS / S3
# ---------------------------------------------------------------------------

RECEIPTS_BUCKET: str = os.environ.get("RECEIPTS_BUCKET", "")
AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

# When set, skip only S3 upload in the update step.
# (Duplicate detection still runs via Mongo receipt_hash exists check.)
BYPASS_S3_UPLOAD: bool = (
    os.environ.get("BYPASS_S3_UPLOAD", "").lower() in ("true", "1", "yes")
    or os.environ.get("BYPASS_S3_AND_DUPLICATE_CHECK", "").lower() in ("true", "1", "yes")
)

# ---------------------------------------------------------------------------
# Bedrock (VLM detect+fraud+extract)
# ---------------------------------------------------------------------------

BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
)
BEDROCK_REGION: str = os.environ.get("BEDROCK_REGION", AWS_REGION)

# When using VLM for fraud+extraction, require receipt validity confidence >= threshold.
FRAUD_CHECK_CONFIDENCE_THRESHOLD: float = float(
    os.environ.get("FRAUD_CHECK_CONFIDENCE_THRESHOLD", "0.8")
)

# ---------------------------------------------------------------------------
# MongoDB (receipt hash, receipt upload history, proof sessions, campaigns/rules)
# ---------------------------------------------------------------------------

MONGODB_URI: Optional[str] = os.environ.get("MONGODB_URI")
MONGODB_DATABASE: str = os.environ.get("MONGODB_DATABASE", "crwd_intelligence")

# Campaign + rules
MONGODB_CRWDS_COLLECTION: str = os.environ.get("MONGODB_CRWDS_COLLECTION", "crwds")
MONGODB_CAMPAIGN_RULES_COLLECTION: Optional[str] = os.environ.get("MONGODB_CAMPAIGN_RULES_COLLECTION")

# Users + block list
MONGODB_USERS_COLLECTION: str = os.environ.get("MONGODB_USERS_COLLECTION", "users")
MONGODB_BLOCK_USERS_COLLECTION: str = os.environ.get("MONGODB_BLOCK_USERS_COLLECTION", "block_users")
MONGODB_ADDED_WORKER_CRWD_MEMBERS_COLLECTION: str = os.environ.get(
    "MONGODB_ADDED_WORKER_CRWD_MEMBERS_COLLECTION", "added_worker_crwd_members"
)

# Receipt hash (duplicate detection)
MONGODB_RECEIPT_HASH_DATABASE: str = os.environ.get("MONGODB_RECEIPT_HASH_DATABASE", "crwdDB")
MONGODB_RECEIPT_HASH_COLLECTION: str = os.environ.get("MONGODB_RECEIPT_HASH_COLLECTION", "receipt_hash")

# Receipt upload history
MONGODB_RECEIPT_UPLOAD_HISTORY_DATABASE: str = os.environ.get(
    "MONGODB_RECEIPT_UPLOAD_HISTORY_DATABASE", "crwdDB"
)
MONGODB_RECEIPT_UPLOAD_HISTORY_COLLECTION: str = os.environ.get(
    "MONGODB_RECEIPT_UPLOAD_HISTORY_COLLECTION", "receipt_upload_history"
)

# Proof sessions for multiproof
MONGODB_PROOF_SESSIONS_DATABASE: str = os.environ.get("MONGODB_PROOF_SESSIONS_DATABASE", "crwdDB")
MONGODB_PROOF_SESSIONS_COLLECTION: str = os.environ.get("MONGODB_PROOF_SESSIONS_COLLECTION", "proof_sessions")

# Optional order duplicate check
MONGODB_ORDER_RECEIPT_REVIEWS_COLLECTION: str = os.environ.get(
    "MONGODB_ORDER_RECEIPT_REVIEWS_COLLECTION", "order_receipt_reviews"
)

# ---------------------------------------------------------------------------
# Chatwoot (used to fetch image bytes from attachment URLs)
# ---------------------------------------------------------------------------

CHATWOOT_IMAGE_HOST: str = os.environ.get("CHATWOOT_IMAGE_HOST", "44.215.200.55")

