"""
MongoDB query functions for CRWD (gigs, users).
No auth. URI: MONGO_URI (default mongodb://localhost:27017). DB: MONGO_DB (default crwd_prod).
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("MONGO_DB", "crwd_prod")

_client = None

# ---------------------------------------------------------------------------
# Agent resources — what Mongo returns means (gigs = crwds collection)
# ---------------------------------------------------------------------------

AGENT_RESOURCES = """
## CRWD data you receive from tools

### Gigs / campaigns (collection: crwds)
Each document is one **gig** or **campaign** a business posts; users apply and complete tasks for pay.

| Field | Meaning |
|-------|--------|
| _id | Gig/campaign id (use for follow-ups) |
| name | Gig title shown to workers |
| description | What the worker must do |
| business_owner_id | Business that created the gig |
| gig_type | `web_based` (online) or `irl` (in-person) |
| price | Payout amount (string in DB) |
| number_of_people | Headcount / slots |
| start_date, end_date | Campaign window |
| duration | Minutes expected |
| type_of_work_proof | e.g. order_receipt, review, attendance |
| status | Active = open; respect isDeleted |
| web_based_status / irl_status | Approval state for that mode |
| address, city, state, postal_code | For IRL gigs |
| time_slots | IRL scheduled times (array) |

When you describe "active gigs" to the user, use **name**, **description**, **price**, **gig_type**, and **deadlines** in plain language—never raw field names unless helpful.

### Users (collection: users)
Lookups by email or phone. Fields may include full_name, email, phone, business_name (business accounts), status, role.
"""


def _get_db():
    global _client
    if _client is None:
        from pymongo import MongoClient
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client[DB_NAME]


def _safe_query(fn) -> list[dict]:
    try:
        return fn()
    except Exception as e:
        logger.error(f"MongoDB query error: {e}")
        return []


def _serialize(docs: list[Any]) -> list[dict]:
    result = []
    for doc in docs:
        if doc is None:
            continue
        clean = {}
        for k, v in doc.items():
            if k == "_id":
                clean[k] = str(v)
            elif hasattr(v, "__iter__") and not isinstance(v, (str, bytes, dict)):
                if isinstance(v, list):
                    clean[k] = [_nested_serialize(x) for x in v]
                else:
                    clean[k] = str(v)
            elif isinstance(v, dict):
                clean[k] = _nested_serialize(v)
            else:
                clean[k] = v
        result.append(clean)
    return result


def _nested_serialize(v: Any) -> Any:
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if k == "_id" and hasattr(x, "__str__"):
                out[k] = str(x)
            elif isinstance(x, dict):
                out[k] = _nested_serialize(x)
            elif isinstance(x, list):
                out[k] = [_nested_serialize(i) for i in x]
            else:
                out[k] = x
        return out
    return v


# Fields returned for gigs so the agent has consistent, readable payloads
_CRWD_PROJECTION = {
    "_id": 1,
    "name": 1,
    "description": 1,
    "business_owner_id": 1,
    "gig_type": 1,
    "price": 1,
    "number_of_people": 1,
    "start_date": 1,
    "end_date": 1,
    "duration": 1,
    "type_of_work_proof": 1,
    "status": 1,
    "web_based_status": 1,
    "irl_status": 1,
    "address": 1,
    "city": 1,
    "state": 1,
    "postal_code": 1,
    "time_slots": 1,
    "isDeleted": 1,
}


def _gig_payload(rows: list[dict]) -> dict:
    """Wrap list with agent context so the LLM knows what the rows represent."""
    return {
        "_type": "gig_campaign_list",
        "_meaning": "Each item is one gig/campaign on CRWD (see AGENT_RESOURCES in system prompt).",
        "items": rows,
    }


def get_active_gigs(limit: int = 5) -> list[dict]:
    """Active gigs from crwds (status Active, not deleted)."""
    db = _get_db()

    def q():
        cur = db.crwds.find(
            {"status": "Active", "isDeleted": {"$ne": True}},
            _CRWD_PROJECTION,
        ).limit(limit)
        return _serialize(list(cur))

    rows = _safe_query(q)
    return _gig_payload(rows)


def get_user_info(identifier: str) -> dict | None:
    db = _get_db()
    try:
        doc = db.users.find_one(
            {"$or": [{"phone": identifier}, {"email": identifier}]},
            {
                "_id": 1,
                "full_name": 1,
                "first_name": 1,
                "last_name": 1,
                "email": 1,
                "phone": 1,
                "status": 1,
                "business_name": 1,
                "isBlocked": 1,
                "isDeleted": 1,
            },
        )
        if not doc:
            return None
        out = _serialize([doc])[0]
        out["_type"] = "user_profile"
        return out
    except Exception as e:
        logger.error(f"MongoDB get_user_info error: {e}")
        return None


def get_campaign_details(campaign_id: str) -> dict | None:
    """One gig/campaign by id or name match (crwds)."""
    db = _get_db()
    try:
        from bson import ObjectId
        try:
            query = {"_id": ObjectId(campaign_id)}
        except Exception:
            query = {"name": {"$regex": campaign_id, "$options": "i"}}
        doc = db.crwds.find_one(query, _CRWD_PROJECTION)
        if not doc:
            return None
        out = _serialize([doc])[0]
        out["_type"] = "gig_campaign_detail"
        out["_meaning"] = "Single gig/campaign; same fields as list items in get_active_gigs."
        return out
    except Exception as e:
        logger.error(f"MongoDB get_campaign_details error: {e}")
        return None


def get_user_gig_history(user_id: str, limit: int = 5) -> list[dict]:
    """Past crwd memberships / applications for a user (added_crwd_members if present)."""
    db = _get_db()

    def q():
        coll = db.added_crwd_members
        cur = coll.find(
            {"user_id": user_id},
            {"_id": 1, "crwd_id": 1, "user_id": 1, "status": 1, "createdAt": 1, "updatedAt": 1},
        ).sort("updatedAt", -1).limit(limit)
        return list(cur)

    rows = _safe_query(q)
    if not rows:
        return _safe_query(
            lambda: _serialize(
                list(
                    db.gig_participations.find(
                        {"user_id": user_id},
                        {"_id": 1, "gig_id": 1, "status": 1, "payment_status": 1, "submitted_at": 1},
                    )
                    .sort("submitted_at", -1)
                    .limit(limit)
                )
            )
        )
    ser = _serialize(rows)
    for r in ser:
        r["_type"] = "user_gig_participation"
    return ser
