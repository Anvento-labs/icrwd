"""
Pytest configuration for local development.
- Loads .env for LangSmith tracing and other secrets
- Suppresses noisy third-party loggers so application logs are easy to read in VS Code
"""

import logging
import os
from pathlib import Path


def _load_env():
    """Load .env file if present (without requiring python-dotenv)."""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def pytest_configure(config):
    _load_env()

    # Suppress verbose third-party loggers
    for noisy in [
        "botocore",
        "boto3",
        "urllib3",
        "langchain_aws",
        "langchain_core",
        "langgraph",
        "httpx",
        "httpcore",
    ]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
