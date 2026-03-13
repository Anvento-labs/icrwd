"""
Execute sub-graph — Generate → Execute → Summarize loop.
Mirrors langgraph-multi-agent/graphs/execute_graph.py.

The LLM in Generate actively decides which tools to call.
Execute dispatches them and feeds results back.
Loop continues until Generate produces no tool calls, then Summarize formats the reply.
"""

from typing import TypedDict, Any
from langgraph.graph import StateGraph, END

from app.nodes.execute import generate_node, execute_node, summarize_node


class ExecuteState(TypedDict):
    messages: list[Any]   # full conversation including tool calls and results
    session_id: str       # for tracing
    plan: str             # predefined plan from orchestrate phase
    persona: str          # classified persona
    reply: str            # final reply written by Summarize


def decide_to_finish(state: ExecuteState) -> str:
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return "Execute"
    return "Summarize"


workflow = StateGraph(ExecuteState)

workflow.add_node("Generate", generate_node.node)
workflow.add_node("Execute", execute_node.node)
workflow.add_node("Summarize", summarize_node.node)

workflow.set_entry_point("Generate")

workflow.add_conditional_edges(
    "Generate",
    decide_to_finish,
    {
        "Execute": "Execute",
        "Summarize": "Summarize",
    },
)

workflow.add_edge("Execute", "Generate")
workflow.add_edge("Summarize", END)

graph = workflow.compile()
