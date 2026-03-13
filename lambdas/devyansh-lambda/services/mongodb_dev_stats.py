"""
MongoDB dev-only stats: connect to cloud cluster and return counts (users, campaigns/crwds).
For local development only. Does not use or change the production MONGODB_URI / mongodb_campaigns flow.

Usage:
  Set MONGODB_DEV_URI (and optionally MONGODB_DEV_DATABASE) in .env, then:
  from services.mongodb_dev_stats import MongoDevStats
  stats = MongoDevStats().get_counts()
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MongoDevStats:
    """
    Dev-only: connect to MongoDB (e.g. Atlas) and return aggregate stats.
    Uses MONGODB_DEV_URI and MONGODB_DEV_DATABASE; production code uses MONGODB_URI.
    """

    def __init__(
        self,
        connection_uri: Optional[str] = None,
        database_name: Optional[str] = None,
        users_collection: str = "users",
        crwds_collection: str = "crwds",
    ):
        """
        Args:
            connection_uri: MongoDB connection string. Defaults to MONGODB_DEV_URI env.
            database_name: Database name. Defaults to MONGODB_DEV_DATABASE or "crwd_intelligence".
            users_collection: Collection name for users (default: users).
            crwds_collection: Collection name for campaigns/crwds (default: crwds).
        """
        self.connection_uri = connection_uri or os.environ.get("MONGODB_DEV_URI")
        self.database_name = database_name or os.environ.get(
            "MONGODB_DEV_DATABASE", "crwd_intelligence"
        )
        self.users_collection = users_collection
        self.crwds_collection = crwds_collection
        self._client = None

    def _get_client(self):
        """Lazy connect; uses its own client (separate from production mongodb_campaigns)."""
        if self.connection_uri is None:
            raise ValueError(
                "MONGODB_DEV_URI is not set. Set it in .env for local development."
            )
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError("pymongo is required. pip install pymongo")
        if self._client is None:
            self._client = MongoClient(self.connection_uri)
        return self._client

    def get_counts(self) -> Dict[str, Any]:
        """
        Return counts for users and campaigns (crwds).
        Excludes soft-deleted documents (isDeleted: True) and uses status: 'Active' where applicable.

        Returns:
            {"users": int, "campaigns": int, "database": str}
        """
        client = self._get_client()
        db = client[self.database_name]
        users_coll = db[self.users_collection]
        crwds_coll = db[self.crwds_collection]

        # Match production-style filters: active, not deleted
        users_count = users_coll.count_documents(
            {"status": "Active", "isDeleted": False}
        )
        campaigns_count = crwds_coll.count_documents(
            {"status": "Active", "isDeleted": False}
        )

        return {
            "users": users_count,
            "campaigns": campaigns_count,
            "database": self.database_name,
        }

    def get_counts_raw(self) -> Dict[str, Any]:
        """
        Return raw total counts (no status/isDeleted filter).
        Useful for debugging.
        """
        client = self._get_client()
        db = client[self.database_name]
        return {
            "users": db[self.users_collection].estimated_document_count(),
            "campaigns": db[self.crwds_collection].estimated_document_count(),
            "database": self.database_name,
        }


def get_dev_counts(
    connection_uri: Optional[str] = None,
    database_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience: return get_counts() from a MongoDevStats instance.
    For local development only.
    """
    return MongoDevStats(
        connection_uri=connection_uri,
        database_name=database_name,
    ).get_counts()
