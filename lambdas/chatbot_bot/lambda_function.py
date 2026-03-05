import json
import base64
import urllib.request
import urllib.error
import boto3

CHATWOOT_BASE_URL = "http://44.215.200.55:3000".rstrip("/")
CHATWOOT_API_TOKEN = "hvsPf6hqwaGVRLBsLD4gugdY"

# System prompt: keep replies short and human, like live support
BEDROCK_SYSTEM = (
    "You are a friendly customer support agent in a live chat. "
    "Reply in 1–3 short sentences. Be warm but concise. No code, no tutorials, no HTML. "
    "For greetings like 'hi' or 'hello', just greet back briefly and offer help."
)

# Try in order: Amazon models (often enabled by default), then Claude
BEDROCK_MODEL_IDS = [
    "amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0",
    "amazon.nova-2-lite-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
]


def handler(event, context):
    try:
        body = event.get("body") or ""
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        payload = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError) as e:
        return _http(400, json.dumps({"error": "Invalid JSON"}))

    event_name = payload.get("event")
    message_type = payload.get("message_type")
    if event_name != "message_created" or message_type != "incoming":
        return _http(200, "")

    content = (payload.get("content") or "").strip()
    conversation = payload.get("conversation") or {}
    account = payload.get("account") or {}
    account_id = account.get("id")
    conversation_id = conversation.get("id")

    if account_id is None or conversation_id is None:
        return _http(200, "")

    headers = {
        "Content-Type": "application/json",
        "api_access_token": CHATWOOT_API_TOKEN,
    }

    if "human handoff" in content.lower():
        _chatwoot_post(
            CHATWOOT_BASE_URL, account_id, conversation_id, None, "messages",
            {"content": "Transferring you to an agent.", "message_type": "outgoing"},
            headers,
        )
        _chatwoot_post(
            CHATWOOT_BASE_URL, account_id, conversation_id, "toggle_status", None,
            {"status": "open"},
            headers,
        )
    else:
        reply = _bedrock_reply(content)
        _chatwoot_post(
            CHATWOOT_BASE_URL, account_id, conversation_id, None, "messages",
            {"content": reply, "message_type": "outgoing"},
            headers,
        )

    return _http(200, "")


def _bedrock_reply(user_message: str) -> str:
    print(f"[bedrock] user_message_len={len(user_message)} trying_models={BEDROCK_MODEL_IDS}")
    client = boto3.client("bedrock-runtime")
    messages = [{"role": "user", "content": [{"text": user_message}]}]
    system = [{"text": BEDROCK_SYSTEM}]
    for model_id in BEDROCK_MODEL_IDS:
        try:
            response = client.converse(
                modelId=model_id,
                messages=messages,
                system=system,
                inferenceConfig={"maxTokens": 150, "temperature": 0.5},
            )
            content = response.get("output", {}).get("message", {}).get("content", [])
            texts = [c["text"] for c in content if c.get("text")]
            reply = " ".join(texts).strip() if texts else ""
            if reply:
                print(f"[bedrock] success model={model_id} reply_len={len(reply)}")
                return reply
            print(f"[bedrock] model={model_id} empty reply")
        except Exception as e:
            print(f"[bedrock] model={model_id} error type={type(e).__name__} error={e}")
    return "hello from lambda"


def _chatwoot_post(base_url, account_id, conversation_id, path_suffix, path_key, data, headers):
    if path_suffix:
        url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/{path_suffix}"
    else:
        url = f"{base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/{path_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        # Log but do not fail the webhook response so Chatwoot does not retry
        print(f"Chatwoot API error {e.code}: {e.read()}")
    except urllib.error.URLError as e:
        print(f"Chatwoot API URLError: {e.reason}")


def _http(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": body,
    }
