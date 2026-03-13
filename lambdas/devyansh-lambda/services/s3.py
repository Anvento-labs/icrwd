"""
S3 operations for receipt storage.
Uses boto3; bucket from config. Lambda execution role for credentials.
"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def upload_receipt(
    bucket: str,
    key: str,
    body: bytes,
    content_type: str = "image/jpeg",
    metadata: Optional[dict] = None,
    region: Optional[str] = None,
) -> str:
    """
    Upload receipt bytes to S3.

    Args:
        bucket: S3 bucket name
        key: Object key (e.g. receipts/{user_id}/{timestamp}_{uuid}.jpg)
        body: Raw bytes
        content_type: MIME type
        metadata: Optional custom metadata (e.g. image_hash)
        region: AWS region (optional)

    Returns:
        S3 URI (s3://bucket/key)

    Raises:
        ClientError: On S3 failure
    """
    if not bucket:
        raise ValueError("RECEIPTS_BUCKET must be set")
    kwargs = {"Bucket": bucket, "Key": key, "Body": body, "ContentType": content_type}
    if metadata:
        kwargs["Metadata"] = {k: str(v) for k, v in metadata.items()}
    client_kwargs = {}
    if region:
        client_kwargs["region_name"] = region
    client = boto3.client("s3", **client_kwargs)
    client.put_object(**kwargs)
    logger.info("Uploaded receipt to s3://%s/%s", bucket, key)
    return f"s3://{bucket}/{key}"


def get_object_bytes(bucket: str, key: str, region: Optional[str] = None) -> bytes:
    """
    Read object from S3 as bytes.

    Args:
        bucket: S3 bucket name
        key: Object key
        region: AWS region (optional)

    Returns:
        Object body bytes
    """
    client_kwargs = {}
    if region:
        client_kwargs["region_name"] = region
    client = boto3.client("s3", **client_kwargs)
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()
