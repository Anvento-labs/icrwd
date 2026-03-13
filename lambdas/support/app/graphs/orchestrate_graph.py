"""
Orchestrate graph — top-level graph.
Mirrors langgraph-multi-agent/graphs/orchestrate_graph.py.

Flow:
  Orchestrate → Classify → Retrieve → Execute (sub-graph bridge)
                                     → Handoff (scam / opt_out)
"""

from langgraph.graph import StateGraph, END

from app.state import GraphState
from app.nodes.orchestrate import (
    orchestrate_node,
    classify_node,
    retrieve_node,
    execute_graph_node,
    handoff_node,
)

workflow = StateGraph(GraphState)

workflow.add_node("Orchestrate", orchestrate_node.node)
workflow.add_node("Classify", classify_node.node)
workflow.add_node("Retrieve", retrieve_node.node)
workflow.add_node("Execute", execute_graph_node.node)
workflow.add_node("Handoff", handoff_node.node)

workflow.set_entry_point("Orchestrate")

workflow.add_conditional_edges(
    "Orchestrate",
    lambda state: state["next"],
    {"Classify": "Classify"},
)

workflow.add_edge("Classify", "Retrieve")

workflow.add_conditional_edges(
    "Retrieve",
    lambda state: state["next"],
    {
        "Execute": "Execute",
        "Handoff": "Handoff",
    },
)

workflow.add_edge("Execute", END)
workflow.add_edge("Handoff", END)

app_graph = workflow.compile()
