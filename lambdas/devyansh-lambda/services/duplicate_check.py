"""
Duplicate image detection using content hash.
Uses DynamoDB table keyed by image_hash. Lambda execution role for credentials.
TODO: set HASH_TABLE_NAME in Lambda env if using DynamoDB.
"""

import hashlib
import logging
from typing import Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def compute_image_hash(image_bytes: bytes) -> str:
    """Compute SHA-256 hash of image bytes (hex)."""
    return hashlib.sha256(image_bytes).hexdigest()


def check_duplicate(
    image_hash: str,
    table_name: str,
    region: Optional[str] = None,
) -> Tuple[bool, bool]:
    """
    Check if hash already exists in DynamoDB. If not, record it.
    If table not configured, treat as no duplicate and do not store.

    Args:
        image_hash: SHA-256 hex of image content
        table_name: DynamoDB table name (partition key: image_hash)
        region: AWS region (optional)

    Returns:
        (is_duplicate, was_stored)
        - is_duplicate: True if hash already in table
        - was_stored: True if we stored the hash (first time); False if duplicate or no table
    """
    if not table_name:
        logger.debug("HASH_TABLE_NAME not set; skipping duplicate check")
        return False, False

    client_kwargs = {}
    if region:
        client_kwargs["region_name"] = region
    dynamodb = boto3.resource("dynamodb", **client_kwargs)
    table = dynamodb.Table(table_name)

    try:
        resp = table.get_item(Key={"image_hash": image_hash})
        if resp.get("Item"):
            logger.info("Image hash already exists; duplicate")
            return True, False
        table.put_item(Item={"image_hash": image_hash})
        logger.info("Stored new image hash; not duplicate")
        return False, True
    except ClientError as e:
        logger.error("DynamoDB error: %s", e)
        raise
