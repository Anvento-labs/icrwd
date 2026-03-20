"""
Retrieve node — pure dict lookup, no LLM.
Looks up the predefined plan for the classified persona.
Routes to Execute (sub-graph) or Handoff. Nothing else.
"""

import logging
from app.state import GraphState
from app.plans import PLANS

logger = logging.getLogger(__name__)

HANDOFF_PERSONAS = {"scam", "opt_out"}


def node(state: GraphState) -> GraphState:
    persona = state.get("persona", "first_timer")
    logger.info(f"[Retrieve] Looking up plan for persona: {persona}")

    plan = PLANS.get(persona, "")
    if not plan:
        logger.warning(f"[Retrieve] No plan found for persona '{persona}', falling back to first_timer")
        plan = PLANS["first_timer"]
    state["plan"] = plan
    logger.info(f"[Retrieve] Plan: {plan[:120]}...")

    if persona in HANDOFF_PERSONAS:
        state["next"] = "Handoff"
    else:
        state["next"] = "Execute"

    logger.info(f"[Retrieve] next={state['next']}")
    state["previous_node"] = "Retrieve"
    return state
