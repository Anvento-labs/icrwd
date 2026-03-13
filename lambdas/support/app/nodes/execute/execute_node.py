"""
Execute node — dispatches tool calls made by the LLM in generate_node.
Mirrors langgraph-multi-agent/nodes/execute/execute_node.py.

Appends ToolMessage results back into messages so the LLM can read
them on the next Generate iteration. Always routes back to Generate.
Errors are fed back as messages (non-blocking) so the LLM can self-correct.
"""

import logging
from langchain_core.messages import ToolMessage
from app.nodes.execute.generate_node import TOOLS

logger = logging.getLogger(__name__)

# Build a name → callable map from the registered tools
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def node(state: dict) -> dict:
    logger.info("[Execute] Dispatching tool calls")

    messages = state.get("messages", [])
    tool_calls = messages[-1].tool_calls

    results = []
    for call in tool_calls:
        tool_name = call["name"]
        tool_args = call["args"]
        tool_call_id = call["id"]

        logger.info(f"[Execute] Calling tool: {tool_name}({tool_args})")

        if tool_name not in TOOLS_BY_NAME:
            content = f"Unknown tool '{tool_name}'. Available tools: {list(TOOLS_BY_NAME.keys())}"
            logger.warning(f"[Execute] {content}")
        else:
            try:
                content = TOOLS_BY_NAME[tool_name].invoke(tool_args)
                logger.info(f"[Execute] {tool_name} returned {len(str(content))} chars")
            except Exception as e:
                content = f"Tool '{tool_name}' raised an error: {e}. Please try a different approach."
                logger.error(f"[Execute] Tool error: {e}")

        results.append(
            ToolMessage(content=str(content), tool_call_id=tool_call_id)
        )

    messages.extend(results)
    state["messages"] = messages
    return state
