"""
Generate node — the LLM actively decides which tools to call.
Mirrors langgraph-multi-agent/nodes/execute/generate_node.py.

The LLM receives the plan and user message, then autonomously decides
which tools to call (or none). All data fetching is driven by the LLM.
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from app.utils import get_llm
from app.tools import mongo_tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions — wrapped so LangChain can bind them to the LLM
# ---------------------------------------------------------------------------

@tool
def get_active_gigs(limit: int = 5) -> str:
    """
    Fetch active gigs/campaigns (Mongo: crwds). Response JSON has _type, _meaning, items[].
    Each item: name, description, price, gig_type (web_based|irl), dates, proof type, etc.
    """
    import json
    results = mongo_tool.get_active_gigs(limit=limit)
    items = results.get("items", []) if isinstance(results, dict) else []
    return json.dumps(results, default=str) if len(items) else "No active gigs found."


@tool
def get_user_info(identifier: str) -> str:
    """
    Look up a user by their phone number or email address.
    Returns their profile and status, or a not-found message.
    """
    import json
    result = mongo_tool.get_user_info(identifier)
    return json.dumps(result, default=str) if result else "No user found with that identifier."


@tool
def get_campaign_details(campaign_id: str) -> str:
    """
    One gig/campaign by Mongo _id or name substring. Same shape as crwds: _type gig_campaign_detail.
    """
    import json
    result = mongo_tool.get_campaign_details(campaign_id)
    return json.dumps(result, default=str) if result else "Campaign not found."


@tool
def get_user_gig_history(user_id: str, limit: int = 5) -> str:
    """
    Retrieve a user's past gig participation history by their user ID.
    Returns a JSON list of past participations with payment status.
    """
    import json
    results = mongo_tool.get_user_gig_history(user_id, limit=limit)
    return json.dumps(results, default=str) if results else "No gig history found for this user."


@tool
def search_kb(query: str) -> str:
    """
    Search the CRWD Knowledge Base for FAQ and company policy information.
    Use this for questions about referral programs, eligibility, payment policies,
    technical support, or any company-specific information.
    """
    from app.utils import get_kb_retriever
    try:
        retriever = get_kb_retriever()
        docs = retriever.invoke(query)
        if docs:
            return "\n\n".join(doc.page_content for doc in docs if doc.page_content)
        return "No relevant information found in the knowledge base."
    except Exception as e:
        logger.error(f"[search_kb] KB error: {e}")
        return "Knowledge base is temporarily unavailable."


TOOLS = [get_active_gigs, get_user_info, get_campaign_details, get_user_gig_history, search_kb]

GENERATE_SYSTEM_PROMPT = """You are a helpful and friendly support agent for CRWD, a gig platform.

Your task is to help the user based on this plan:
<plan>
{plan}
</plan>

""" + mongo_tool.AGENT_RESOURCES.strip() + """

You have access to tools to fetch live data. Use them when the plan requires it:
- get_active_gigs: active gigs/campaigns (payload includes _meaning + items)
- get_user_info: user by phone/email (_type user_profile)
- get_campaign_details: one gig by id or name (_type gig_campaign_detail)
- get_user_gig_history: user's past gigs/memberships
- search_kb: FAQ and company policy

Guidelines:
- Follow the plan step by step
- Use tools when you need real data to answer the user's question
- Be warm, concise, and action-oriented
- Do not mention internal systems (MongoDB, Knowledge Base, LLM) to the user
- Keep responses under 150 words unless detailed information is truly needed"""


def node(state: dict) -> dict:
    logger.info("[Generate] Entering generate node")

    plan = state.get("plan", "")
    messages = state.get("messages", [])

    system_prompt = GENERATE_SYSTEM_PROMPT.format(plan=plan).strip()

    if not messages:
        messages = [HumanMessage(content="Begin!")]

    llm = get_llm("smart")
    llm_with_tools = llm.bind_tools(TOOLS)

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ])

    chain = prompt | llm_with_tools
    result = chain.invoke({"messages": messages})

    messages.append(result)
    state["messages"] = messages
    logger.info(f"[Generate] tool_calls={bool(result.tool_calls)}")
    return state
