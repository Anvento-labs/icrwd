"""
Summarize node — formats the final reply from the LLM's last message.
Mirrors langgraph-multi-agent/nodes/execute/summarize_node.py.

The Generate node has finished (no more tool calls). The last AI message
contains either a direct answer or a verbose summary of tool results.
This node uses a fast LLM pass to produce a clean, warm, concise reply
and writes it to state["reply"].
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.utils import get_llm

logger = logging.getLogger(__name__)

SUMMARIZE_SYSTEM_PROMPT = """You are a friendly support agent for CRWD, a gig platform.

Take the assistant's draft response below and produce a final, polished reply to send to the user.

Rules:
- Keep it warm, concise, and action-oriented (under 150 words unless detail is truly needed)
- Do not mention internal systems (MongoDB, Knowledge Base, tools) to the user
- Do not repeat information unnecessarily
- Preserve all specific details (gig names, amounts, dates) from the draft
- If the draft is already polished, return it as-is"""


def node(state: dict) -> dict:
    logger.info("[Summarize] Formatting final reply")

    messages = state.get("messages", [])

    # The last AI message contains the LLM's final answer
    last_ai_content = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and not hasattr(msg, "tool_call_id"):
            last_ai_content = msg.content or ""
            break

    if not last_ai_content:
        logger.warning("[Summarize] No AI content found in messages, using fallback")
        state["reply"] = "I'm having trouble formulating a response right now. Please try again."
        return state

    llm = get_llm("fast")

    response = llm.invoke([
        SystemMessage(content=SUMMARIZE_SYSTEM_PROMPT),
        HumanMessage(content=f"Draft response:\n{last_ai_content}"),
    ])

    reply = response.content.strip()
    logger.info(f"[Summarize] Final reply: {len(reply)} chars")

    state["reply"] = reply
    return state
