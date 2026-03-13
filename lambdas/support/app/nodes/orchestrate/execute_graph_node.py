"""
ExecuteGraphNode — bridge between the orchestrate graph and the execute sub-graph.
Mirrors langgraph-multi-agent/nodes/orchestrate/execute_graph_node.py.
"""

import logging
from langchain_core.messages import HumanMessage
from app.state import GraphState
from app.graphs import execute_graph

logger = logging.getLogger(__name__)


def node(state: GraphState) -> GraphState:
    logger.info("[ExecuteGraphNode] Invoking execute sub-graph")

    inputs = {
        "messages": [HumanMessage(content=state.get("message", ""))],
        "session_id": state.get("session_id", ""),
        "plan": state.get("plan", ""),
        "persona": state.get("persona", ""),
        "reply": "",
    }

    final_reply = ""

    for s in execute_graph.graph.stream(inputs, {"recursion_limit": 20}):
        for key, value in s.items():
            logger.info(f"[ExecuteGraphNode] sub-graph node completed: {key}")
            if key == "Summarize":
                final_reply = value.get("reply", "")

    state["reply"] = final_reply or "I'm having trouble formulating a response right now."
    state["handoff"] = False
    state["previous_node"] = "Execute"

    logger.info(f"[ExecuteGraphNode] Final reply: {len(state['reply'])} chars")
    return state
