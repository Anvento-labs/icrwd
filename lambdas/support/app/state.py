from typing import TypedDict, List, Any, NotRequired


class GraphState(TypedDict):
    message: str          # raw incoming user message
    messages: List[Any]   # conversation history (future: multi-turn)
    session_id: str       # session tracking
    previous_node: str    # drives Orchestrate routing
    next: str             # routing target used by conditional edges
    persona: str          # classified persona key
    plan: str             # retrieved predefined plan text
    reply: str            # final reply to send to user
    handoff: bool         # whether to trigger human handoff
    user: NotRequired[dict[str, Any]]  # Mongo user profile loaded at init; {} if not found
