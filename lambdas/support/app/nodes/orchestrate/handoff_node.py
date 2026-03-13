"""
Handoff node — no LLM.
Returns a fixed message and sets handoff=True so lambda_function
can trigger the human agent assignment in Chatwoot.
"""

import logging
from app.state import GraphState

logger = logging.getLogger(__name__)

HANDOFF_MESSAGES = {
    "scam": (
        "We have flagged this conversation and it is being escalated to our team for review. "
        "Further activity may be reported."
    ),
    "opt_out": (
        "We have received your request to opt out. You will be removed from our messaging list. "
        "If you ever want to re-join, feel free to reach out. Thank you!"
    ),
}

DEFAULT_HANDOFF_MESSAGE = (
    "I am connecting you with a member of our team who will be able to assist you further. "
    "Please hold on."
)


def node(state: GraphState) -> GraphState:
    persona = state.get("persona", "")
    logger.info(f"[Handoff] Triggering handoff for persona: {persona}")

    reply = HANDOFF_MESSAGES.get(persona, DEFAULT_HANDOFF_MESSAGE)

    state["reply"] = reply
    state["handoff"] = True
    state["previous_node"] = "Handoff"
    return state
