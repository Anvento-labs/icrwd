import boto3
from langchain_aws import ChatBedrockConverse, AmazonKnowledgeBasesRetriever

BEDROCK_REGION = "us-east-1" 

def get_llm(model_type="fast"):
    """
    Returns Bedrock Chat Model using the 'Converse' API.
    This fixes 'ValidationException' errors by standardizing input format.
    """
    client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

    if model_type == "smart":
        model_id = "amazon.nova-lite-v1:0"
    else:
        model_id = "amazon.nova-micro-v1:0"

    return ChatBedrockConverse(
        client=client,
        model_id=model_id,
        temperature=0,
        max_tokens=1024
    )

def get_kb_retriever(kb_id):
    """
    Connects to Amazon Bedrock Knowledge Base.
    """
    return AmazonKnowledgeBasesRetriever(
        knowledge_base_id=kb_id,
        region_name=BEDROCK_REGION,
        retrieval_config={
            "vectorSearchConfiguration": {
                "numberOfResults": 4
            }
        },
    )