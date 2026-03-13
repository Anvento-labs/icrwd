"""
LangGraph workflow for receipt verification.

Graph 1 (legacy): START -> input_s3_duplicate -> (conditional) -> extraction -> (conditional) -> validation | validation_bypass -> END.

Graph 2 (proof pipeline): START -> get_mongo -> (if duplicate -> update_mongo -> END else detect_image -> (if not valid -> update_mongo -> END else validation -> update_mongo -> END)).
"""

import logging
from typing import Literal

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from state import AIEngineState
from nodes import (
    node_input_s3_duplicate,
    node_extraction,
    node_validation,
    node_validation_bypass,
    node_get_mongo,
    node_detect_image,
    node_update_mongo,
)

logger = logging.getLogger(__name__)

# Node names (legacy graph)
NODE_INPUT_S3_DUPLICATE = "input_s3_duplicate"
NODE_EXTRACTION = "extraction"
NODE_VALIDATION = "validation"
NODE_VALIDATION_BYPASS = "validation_bypass"

# Node names (proof pipeline)
NODE_GET_MONGO = "get_mongo"
NODE_DETECT_IMAGE = "detect_image"
NODE_UPDATE_MONGO = "update_mongo"


def _route_after_input(state: AIEngineState) -> Literal["__end__", "extraction"]:
    """
    Conditional edge after input_s3_duplicate: skip extraction and validation if duplicate or invalid.
    Returns END to stop, or NODE_EXTRACTION to continue to extraction.
    """
    is_dup = state.get("is_duplicate")
    input_status = state.get("input_validation_status")
    logger.info(
        "Conditional edge after input_s3_duplicate | is_duplicate=%s | input_validation_status=%s",
        is_dup,
        input_status,
    )
    if state.get("is_duplicate"):
        logger.info("Conditional edge: routing to END (duplicate receipt)")
        return END
    if state.get("input_validation_status") != "valid":
        logger.info("Conditional edge: routing to END (invalid input)")
        return END
    logger.info("Conditional edge: routing to node extraction")
    return NODE_EXTRACTION  # "extraction"


def _route_after_extraction(state: AIEngineState) -> Literal["validation", "validation_bypass"]:
    """
    Conditional edge after extraction: if bypass_validation then validation_bypass else validation.
    """
    bypass = state.get("bypass_validation")
    logger.info("Conditional edge after extraction | bypass_validation=%s", bypass)
    if bypass:
        logger.info("Conditional edge: routing to validation_bypass (BYPASS_VALIDATION=true)")
        return NODE_VALIDATION_BYPASS
    logger.info("Conditional edge: routing to validation")
    return NODE_VALIDATION


def build_graph() -> StateGraph:
    """Build the receipt verification StateGraph (not compiled)."""
    builder = StateGraph(AIEngineState)

    builder.add_node(NODE_INPUT_S3_DUPLICATE, node_input_s3_duplicate)
    builder.add_node(NODE_EXTRACTION, node_extraction)
    builder.add_node(NODE_VALIDATION, node_validation)
    builder.add_node(NODE_VALIDATION_BYPASS, node_validation_bypass)

    builder.add_edge(START, NODE_INPUT_S3_DUPLICATE)
    builder.add_conditional_edges(
        NODE_INPUT_S3_DUPLICATE,
        _route_after_input,
        path_map={END: END, NODE_EXTRACTION: NODE_EXTRACTION},
    )
    builder.add_conditional_edges(
        NODE_EXTRACTION,
        _route_after_extraction,
        path_map={NODE_VALIDATION: NODE_VALIDATION, NODE_VALIDATION_BYPASS: NODE_VALIDATION_BYPASS},
    )
    builder.add_edge(NODE_VALIDATION, END)
    builder.add_edge(NODE_VALIDATION_BYPASS, END)

    return builder


def get_compiled_graph():
    """Return the compiled graph (cached on first call)."""
    if get_compiled_graph._graph is None:
        logger.info("Compiling LangGraph workflow (first invocation)")
        get_compiled_graph._graph = build_graph().compile()
    return get_compiled_graph._graph


get_compiled_graph._graph = None


# --- Proof pipeline (4-node) ---


def _route_after_get_mongo(state: AIEngineState) -> Literal["__end__", "detect_image", "update_mongo"]:
    """
    After get_mongo: if duplicate -> update_mongo (to log) -> END; else -> detect_image.
    Plan: if duplicate we still go to update_mongo then END so history is written.
    """
    is_dup = state.get("is_duplicate")
    logger.info("[workflow] After get_mongo | is_duplicate=%s", is_dup)
    if is_dup:
        logger.info("[workflow] Routing to update_mongo (duplicate)")
        return NODE_UPDATE_MONGO
    logger.info("[workflow] Routing to detect_image")
    return NODE_DETECT_IMAGE


def _route_after_detect(state: AIEngineState) -> Literal["update_mongo", "validation"]:
    """After detect_image: if not valid -> update_mongo -> END; else -> validation."""
    valid = state.get("is_valid_image")
    logger.info("[workflow] After detect_image | is_valid_image=%s", valid)
    if not valid:
        logger.info("[workflow] Routing to update_mongo (invalid/fraud)")
        return NODE_UPDATE_MONGO
    logger.info("[workflow] Routing to validation")
    return NODE_VALIDATION


def build_proof_graph() -> StateGraph:
    """Build the 4-node proof pipeline StateGraph (get_mongo -> detect_image -> validation -> update_mongo)."""
    builder = StateGraph(AIEngineState)

    builder.add_node(NODE_GET_MONGO, node_get_mongo)
    builder.add_node(NODE_DETECT_IMAGE, node_detect_image)
    builder.add_node(NODE_VALIDATION, node_validation)
    builder.add_node(NODE_UPDATE_MONGO, node_update_mongo)

    builder.add_edge(START, NODE_GET_MONGO)
    builder.add_conditional_edges(
        NODE_GET_MONGO,
        _route_after_get_mongo,
        path_map={NODE_UPDATE_MONGO: NODE_UPDATE_MONGO, NODE_DETECT_IMAGE: NODE_DETECT_IMAGE},
    )
    builder.add_conditional_edges(
        NODE_DETECT_IMAGE,
        _route_after_detect,
        path_map={NODE_UPDATE_MONGO: NODE_UPDATE_MONGO, NODE_VALIDATION: NODE_VALIDATION},
    )
    builder.add_edge(NODE_VALIDATION, NODE_UPDATE_MONGO)
    builder.add_edge(NODE_UPDATE_MONGO, END)

    return builder


def get_compiled_graph_proof():
    """Return the compiled proof pipeline graph (cached on first call)."""
    if get_compiled_graph_proof._graph is None:
        logger.info("Compiling LangGraph proof pipeline (first invocation)")
        get_compiled_graph_proof._graph = build_proof_graph().compile()
    return get_compiled_graph_proof._graph


get_compiled_graph_proof._graph = None
