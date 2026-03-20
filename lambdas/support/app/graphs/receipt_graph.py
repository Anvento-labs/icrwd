"""
LangGraph workflow for the `support` receipt proof pipeline.

Ports devyansh-lambda's active proof pipeline (Graph 2) into the support lambda:
START -> get_mongo -> (duplicate? update_mongo : detect_image)
       -> detect_image -> (is_valid_image? validation : update_mongo)
       -> validation -> update_mongo -> END
"""

from typing import Any, Dict, Literal

from langgraph.constants import END
from langgraph.graph import StateGraph

from app.receipt_state import ReceiptGraphState
from app.nodes.receipt import node_get_mongo, node_detect_image, node_validation, node_update_mongo


def _route_after_get_mongo(state: Dict[str, Any]) -> Literal["update_mongo", "detect_image"]:
    return "update_mongo" if state.get("is_duplicate") else "detect_image"


def _route_after_detect_image(state: Dict[str, Any]) -> Literal["validation", "update_mongo"]:
    return "validation" if state.get("is_valid_image") else "update_mongo"


workflow = StateGraph(ReceiptGraphState)

workflow.add_node("get_mongo", node_get_mongo.node)
workflow.add_node("detect_image", node_detect_image.node)
workflow.add_node("validation", node_validation.node)
workflow.add_node("update_mongo", node_update_mongo.node)

workflow.set_entry_point("get_mongo")

workflow.add_conditional_edges(
    "get_mongo",
    _route_after_get_mongo,
    path_map={"update_mongo": "update_mongo", "detect_image": "detect_image"},
)

workflow.add_conditional_edges(
    "detect_image",
    _route_after_detect_image,
    path_map={"validation": "validation", "update_mongo": "update_mongo"},
)

workflow.add_edge("validation", "update_mongo")
workflow.add_edge("update_mongo", END)

graph = workflow.compile()

