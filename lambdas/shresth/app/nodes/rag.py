from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.utils import get_llm, get_kb_retriever

def rag_node(state):
        
    question = state["question"]
    
    KB_ID = "LAOP9XCNY9" 
    
    try:
        print(f"Searching KB {KB_ID} in us-east-1 for: {question}")
        retriever = get_kb_retriever(KB_ID)
        docs = retriever.invoke(question)
        
        if not docs:
            print("No documents found in KB.")
            return {"generation": "I couldn't find any information on that in the Knowledge Base."}
            
        context_text = "\n\n".join([doc.page_content for doc in docs])
        
    except Exception as e:
        print(f"KB Error: {e}")
        return {"generation": f"Error connecting to Knowledge Base: {str(e)}"}
    
    llm = get_llm("smart")
    
    template = """You are a helpful assistant. 
    Answer the question based ONLY on the context provided below.
    
    Context:
    {context}
    
    Question: 
    {question}
    
    Answer:"""
    
    prompt = ChatPromptTemplate.from_template(template)
    rag_chain = prompt | llm | StrOutputParser()
    
    response = rag_chain.invoke({"context": context_text, "question": question})
    
    return {"generation": response, "documents": docs}