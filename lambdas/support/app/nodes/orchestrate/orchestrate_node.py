"""
Orchestrate node — pure router, no LLM calls.
Reads previous_node from state and sets next to direct the conditional edge.
Mirrors the pattern in langgraph-multi-agent/nodes/orchestrate/orchestrate_node.py.
"""

import logging
from app.state import GraphState

logger = logging.getLogger(__name__)


def node(state: GraphState) -> GraphState:
    previous_node = state.get("previous_node")

    logger.info(f"[Orchestrate] previous_node={previous_node}")

    if previous_node is None:
        # First turn: always classify the incoming message
        state["next"] = "Classify"
    else:
        # Future multi-turn routing can be added here (e.g. revise, memorize)
        state["next"] = "Classify"

    state["previous_node"] = "Orchestrate"
    return state
