import boto3
from langchain_aws import ChatBedrockConverse, AmazonKnowledgeBasesRetriever

BEDROCK_REGION = "us-east-1"
KB_ID = "LAOP9XCNY9"


def get_llm(model_type="fast"):
    """
    Returns a Bedrock Chat model via the Converse API.
    fast  → amazon.nova-micro-v1:0  (classify, orchestrate)
    smart → amazon.nova-lite-v1:0   (respond)
    """
    client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

    model_id = "amazon.nova-lite-v1:0" if model_type == "smart" else "amazon.nova-micro-v1:0"

    return ChatBedrockConverse(
        client=client,
        model_id=model_id,
        temperature=0,
        max_tokens=1024,
    )


def get_kb_retriever(kb_id=KB_ID):
    """
    Connects to Amazon Bedrock Knowledge Base (FAQ / company info).
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
