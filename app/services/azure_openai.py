"""
PULSE - Azure OpenAI Service
Provides LLM access via Azure OpenAI through LangChain.
Uses Azure RBAC (DefaultAzureCredential) — no API keys required.
Required Role: "Cognitive Services OpenAI User" on the Azure OpenAI resource.
"""

import logging
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from langchain_openai import AzureChatOpenAI
from app.config import settings

logger = logging.getLogger("pulse.azure_openai")

# Azure AD token provider scoped to Azure Cognitive Services
_credential = DefaultAzureCredential()
_token_provider = get_bearer_token_provider(
    _credential, "https://cognitiveservices.azure.com/.default"
)


def get_llm(
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> AzureChatOpenAI:
    """
    Returns an AzureChatOpenAI instance authenticated via Azure RBAC.
    """
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai.endpoint,
        azure_deployment=settings.azure_openai.deployment_name,
        api_version=settings.azure_openai.api_version,
        azure_ad_token_provider=_token_provider,
        temperature=temperature or settings.agent.temperature,
        max_tokens=max_tokens or settings.agent.max_tokens,
        model=settings.azure_openai.model_name,
    )


# Pre-configured instances for convenience
def get_creative_llm() -> AzureChatOpenAI:
    """Higher temperature for creative writing tasks."""
    return get_llm(temperature=0.7)


def get_analytical_llm() -> AzureChatOpenAI:
    """Lower temperature for analytical / fact-checking tasks."""
    return get_llm(temperature=0.1)
