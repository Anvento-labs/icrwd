"""
Pure Chatwoot API functions — no LangGraph state, no side effects beyond HTTP.
Called exclusively from lambda_function.py.
"""

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def _request(method: str, url: str, headers: dict, data: dict | None = None) -> dict | None:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        logger.error(f"Chatwoot HTTP {e.code} [{method} {url}]: {e.read().decode()}")
        return None
    except urllib.error.URLError as e:
        logger.error(f"Chatwoot URLError [{method} {url}]: {e.reason}")
        return None


def _conversation_url(base_url: str, account_id: int, conversation_id: int, endpoint: str) -> str:
    return f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/{endpoint}"


def send_message(
    base_url: str,
    account_id: int,
    conversation_id: int,
    content: str,
    headers: dict,
    message_type: str = "outgoing",
) -> dict | None:
    """Post a message to a Chatwoot conversation. Returns the created message dict."""
    url = _conversation_url(base_url, account_id, conversation_id, "messages")
    return _request("POST", url, headers, {"content": content, "message_type": message_type})


def delete_message(
    base_url: str,
    account_id: int,
    conversation_id: int,
    message_id: int,
    headers: dict,
) -> None:
    """Delete a message from a Chatwoot conversation."""
    url = _conversation_url(base_url, account_id, conversation_id, f"messages/{message_id}")
    _request("DELETE", url, headers)


def toggle_status(
    base_url: str,
    account_id: int,
    conversation_id: int,
    status: str,
    headers: dict,
) -> None:
    """Toggle conversation status (e.g. 'open', 'resolved', 'pending')."""
    url = _conversation_url(base_url, account_id, conversation_id, "toggle_status")
    _request("POST", url, headers, {"status": status})


def assign_agent(
    base_url: str,
    account_id: int,
    conversation_id: int,
    assignee_id: int,
    headers: dict,
) -> None:
    """Assign a conversation to a specific agent."""
    url = _conversation_url(base_url, account_id, conversation_id, "assignments")
    _request("POST", url, headers, {"assignee_id": assignee_id})
