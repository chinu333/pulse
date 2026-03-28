"""
PULSE - Azure OpenAI Embeddings Service
Provides embedding generation via Azure OpenAI.
Uses Azure RBAC (DefaultAzureCredential) — no API keys required.
Required Role: "Cognitive Services OpenAI User" on the Azure OpenAI resource.
"""

import logging
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from langchain_openai import AzureOpenAIEmbeddings
from app.config import settings

logger = logging.getLogger("pulse.embeddings")

# Azure AD token provider scoped to Azure Cognitive Services
_credential = DefaultAzureCredential()
_token_provider = get_bearer_token_provider(
    _credential, "https://cognitiveservices.azure.com/.default"
)


def get_embeddings() -> AzureOpenAIEmbeddings:
    """
    Returns an AzureOpenAIEmbeddings instance authenticated via Azure RBAC.
    """
    return AzureOpenAIEmbeddings(
        azure_endpoint=settings.azure_openai.endpoint,
        azure_deployment=settings.azure_openai.embedding_deployment,
        api_version=settings.azure_openai.api_version,
        azure_ad_token_provider=_token_provider,
        model=settings.azure_openai.embedding_model,
    )
