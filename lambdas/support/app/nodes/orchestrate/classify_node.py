"""
Classify node — uses LLM (fast) to detect the user's persona from the incoming message.
Sets state["persona"] to one of the 10 known persona keys.
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.state import GraphState
from app.utils import get_llm

logger = logging.getLogger(__name__)

PERSONAS = [
    "first_timer",
    "returning_user",
    "referral",
    "proof_submission",
    "mid_gig_support",
    "ineligible",
    "payment_inquiry",
    "technical_issue",
    "scam",
    "opt_out",
]

SYSTEM_PROMPT = f"""You are a message classifier for CRWD, a gig platform that recruits people to perform tasks like distributing flyers or attending events.

Classify the user's message into exactly ONE of these personas:

- first_timer: New or curious user — what CRWD is, how to join, how gigs work, what gigs are available, OR generic how-payment-works questions ("How do I get paid?") with no claim about THEIR money missing. Prefer first_timer whenever they sound like they're exploring, not referencing "my" completed gigs.
- returning_user: Clearly an existing user — my past gigs, my account, gigs I already did, log in issues as a member, "again", "another gig" after having done one
- referral: User asking about a referral code, referral rewards, or how the referral program works
- proof_submission: User is trying to submit proof of gig completion (receipts, screenshots, photos)
- mid_gig_support: User is currently doing a gig and has a question or problem mid-task
- ineligible: User is not eligible for a gig and is questioning why or asking about alternatives
- payment_inquiry: ONLY when asking about THEIR OWN payment problem — missing/delayed payout, "where is my money", "I wasn't paid", pending transfer for a completed gig
- technical_issue: User is reporting a technical problem (app crash, link broken, can't log in)
- scam: User is sending suspicious, threatening, or clearly fraudulent messages
- opt_out: User explicitly wants to stop receiving messages or unsubscribe

Respond with ONLY the persona key, nothing else. Example: returning_user"""


def node(state: GraphState) -> GraphState:
    message = state.get("message", "")
    logger.info(f"[Classify] Classifying message: {message[:100]}")

    llm = get_llm("fast")

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=message),
    ])

    raw = response.content.strip().lower().replace("-", "_")

    persona = raw if raw in PERSONAS else "first_timer"

    if raw not in PERSONAS:
        logger.warning(f"[Classify] Unknown persona '{raw}', defaulting to first_timer")

    logger.info(f"[Classify] Classified as: {persona}")

    state["persona"] = persona
    state["previous_node"] = "Classify"
    return state
