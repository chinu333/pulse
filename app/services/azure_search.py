"""
PULSE - Azure AI Search Service
Provides vector search / RAG retrieval via Azure AI Search.
Uses Azure RBAC (DefaultAzureCredential) — no API keys required.
Required Role: "Search Index Data Reader" on the Azure AI Search resource.
"""

import logging
from typing import Any
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from langchain_community.vectorstores.azuresearch import AzureSearch
from app.config import settings
from app.services.embeddings import get_embeddings

logger = logging.getLogger("pulse.azure_search")

# Azure AD credential for Search service
_credential = DefaultAzureCredential()


def get_vector_store() -> AzureSearch:
    """
    Returns an AzureSearch vector store instance authenticated via Azure RBAC.
    """
    return AzureSearch(
        azure_search_endpoint=settings.azure_search.endpoint,
        azure_search_key=None,
        index_name=settings.azure_search.index_name,
        embedding_function=get_embeddings(),
        search_type="similarity",
        azure_search_credential=_credential,
    )


async def search_knowledge_base(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Perform a vector similarity search against the knowledge base.
    Returns a list of relevant documents with scores.
    Gracefully returns an empty list if the index is empty or unavailable.
    """
    if settings.demo_mode:
        return _mock_search_results(query)

    try:
        store = get_vector_store()
        results = store.similarity_search_with_relevance_scores(query, k=top_k)

        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": round(score, 3),
            }
            for doc, score in results
        ]
    except Exception as exc:
        logger.warning("Azure AI Search unavailable or index empty — returning no results: %s", exc)
        return []


def _mock_search_results(query: str) -> list[dict[str, Any]]:
    """Provides realistic mock search results for demo mode."""
    mock_docs = [
        {
            "content": (
                "E.W. Scripps Company operates 61 local television stations in 41 markets, "
                "reaching approximately 30% of U.S. households. The company's broadcast portfolio "
                "includes ABC, NBC, CBS, FOX, and CW affiliates, along with several multicast networks."
            ),
            "metadata": {"source": "corporate_profile.pdf", "page": 1, "category": "company_info"},
            "relevance_score": 0.94,
        },
        {
            "content": (
                "Scripps' national networks division includes Scripps News, ION, Bounce, Grit, "
                "Court TV, Laff, TrueReal, ION Mystery, ION Adventure, Defy TV, and Newsy. "
                "ION is the #1 most-watched ad-supported premium cable network in prime time."
            ),
            "metadata": {"source": "networks_overview.pdf", "page": 3, "category": "networks"},
            "relevance_score": 0.91,
        },
        {
            "content": (
                "Breaking news coverage protocols require verification from at least two independent "
                "sources before publication. All breaking stories must include geographic impact "
                "assessment, affected population count, and emergency response status."
            ),
            "metadata": {"source": "editorial_guidelines.pdf", "page": 12, "category": "editorial_policy"},
            "relevance_score": 0.88,
        },
        {
            "content": (
                "The FCC requires broadcast stations to maintain public inspection files and comply "
                "with rules regarding political advertising, children's programming, and equal "
                "employment opportunities. Stations must also adhere to sponsorship identification rules."
            ),
            "metadata": {"source": "compliance_handbook.pdf", "page": 7, "category": "compliance"},
            "relevance_score": 0.85,
        },
        {
            "content": (
                "SEO best practices for Scripps digital content: headlines should be 55-70 characters, "
                "meta descriptions 150-160 characters. Include location + topic in headlines for local "
                "stories. Use structured data markup for news articles (NewsArticle schema)."
            ),
            "metadata": {"source": "digital_style_guide.pdf", "page": 22, "category": "seo"},
            "relevance_score": 0.82,
        },
    ]
    return mock_docs
