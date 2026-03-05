from langgraph.graph import StateGraph, END
from app.state import GraphState
from app.nodes.router import route_question
from app.nodes.rag import rag_node
from app.nodes.handoff import handoff_node

workflow = StateGraph(GraphState)

workflow.add_node("rag", rag_node)
workflow.add_node("handoff", handoff_node)

workflow.set_conditional_entry_point(
    route_question,
    {
        "rag": "rag",
        "handoff": "handoff",
    }
)


workflow.add_edge("rag", END)
workflow.add_edge("handoff", END)


app_graph = workflow.compile()