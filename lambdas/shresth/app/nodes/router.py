from typing import Literal
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from app.utils import get_llm

class RouteQuery(BaseModel):
    """Route a user query to the most relevant datasource."""
    datasource: Literal["vectorstore", "handoff"] = Field(
        ...,
        description="Choose 'vectorstore' for data questions or 'handoff' for human help/safety."
    )

def route_question(state):    
    llm = get_llm(model_type="fast") 

    parser = JsonOutputParser(pydantic_object=RouteQuery)

    system_prompt = """You are a routing assistant.
    If the question is about campaigns, vendors, budgets, products, or payments: return 'vectorstore'.
    If the question is about scams, fraud, legal threats, or asking for a human: return 'handoff'.
    
    Output ONLY valid JSON with a single key 'datasource'.
    Example: {{"datasource": "vectorstore"}}
    
    \n{format_instructions}"""

    prompt = PromptTemplate(
        template=system_prompt + "\n\nQuestion: {question}",
        input_variables=["question"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    question_router = prompt | llm | parser

    question = state["question"]
    try:
        source = question_router.invoke({"question": question})
        
        source_str = str(source).lower()
        if "handoff" in source_str:
            return "handoff"
        return "rag"
        
    except Exception as e:
        print(f"Router Error: {e}. Defaulting to RAG.")
        return "rag"