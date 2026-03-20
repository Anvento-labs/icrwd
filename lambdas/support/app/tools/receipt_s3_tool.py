"""
S3 helpers for the `support` receipt proof pipeline.

Ports `upload_receipt` from `lambdas/devyansh-lambda/services/s3.py`.
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

    Returns: `s3://{bucket}/{key}`
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

