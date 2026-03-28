"""
PULSE - Azure AI Search Index Setup & Seeding Script
=====================================================
Creates the 'pulse-knowledge-base' index in Azure AI Search,
generates embeddings for all knowledge base documents, and uploads them.

Uses Azure RBAC (DefaultAzureCredential) — no API keys.
Required Roles:
  - Azure AI Search: "Search Index Data Contributor" + "Search Service Contributor"
  - Azure OpenAI:    "Cognitive Services OpenAI User"

Usage:
    python -m scripts.seed_index
"""

import json
import logging
import sys
import time
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SearchFieldDataType,
)

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.embeddings import get_embeddings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pulse.seed_index")

# ── Constants ────────────────────────────────────────────────
KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "knowledge_base.json"
EMBEDDING_DIMENSIONS = 1536  # text-embedding-ada-002 output dimensions
INDEX_NAME = settings.azure_search.index_name
SEARCH_ENDPOINT = settings.azure_search.endpoint


def create_index(index_client: SearchIndexClient) -> None:
    """
    Creates the search index with vector fields.
    If the index already exists, it will be deleted and recreated.
    """
    # Check if index exists
    try:
        existing = index_client.get_index(INDEX_NAME)
        if existing:
            logger.warning(f"Index '{INDEX_NAME}' already exists — deleting and recreating...")
            index_client.delete_index(INDEX_NAME)
            time.sleep(2)
    except Exception:
        pass  # Index doesn't exist, proceed to create

    # Define fields
    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SearchableField(
            name="title",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        SimpleField(
            name="category",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SimpleField(
            name="source",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="default-vector-profile",
        ),
    ]

    # Vector search configuration
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(name="default-hnsw"),
        ],
        profiles=[
            VectorSearchProfile(
                name="default-vector-profile",
                algorithm_configuration_name="default-hnsw",
            ),
        ],
    )

    # Create the index
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
    )

    result = index_client.create_index(index)
    logger.info(f"✅ Index '{result.name}' created successfully")


def load_knowledge_base() -> list[dict]:
    """Load knowledge base documents from JSON file."""
    with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
        docs = json.load(f)
    logger.info(f"📄 Loaded {len(docs)} documents from knowledge base")
    return docs


def generate_embeddings(docs: list[dict]) -> list[dict]:
    """Generate embeddings for each document's content field."""
    embeddings_model = get_embeddings()

    logger.info("🔄 Generating embeddings via Azure OpenAI...")
    contents = [doc["content"] for doc in docs]
    vectors = embeddings_model.embed_documents(contents)

    for doc, vector in zip(docs, vectors):
        doc["content_vector"] = vector

    logger.info(f"✅ Generated {len(vectors)} embeddings (dim={len(vectors[0])})")
    return docs


def upload_documents(search_client: SearchClient, docs: list[dict]) -> None:
    """Upload documents with embeddings to the search index."""
    logger.info(f"📤 Uploading {len(docs)} documents to index '{INDEX_NAME}'...")
    result = search_client.upload_documents(documents=docs)

    succeeded = sum(1 for r in result if r.succeeded)
    failed = sum(1 for r in result if not r.succeeded)
    logger.info(f"✅ Upload complete: {succeeded} succeeded, {failed} failed")

    if failed > 0:
        for r in result:
            if not r.succeeded:
                logger.error(f"   ❌ Document '{r.key}' failed: {r.error_message}")


def verify_index(search_client: SearchClient) -> None:
    """Run a quick test search to verify the index is working."""
    logger.info("🔍 Verifying index with a test search...")
    time.sleep(2)  # Allow time for indexing

    results = search_client.search(
        search_text="editorial guidelines",
        top=3,
        select=["id", "title", "category"],
    )

    count = 0
    for result in results:
        count += 1
        logger.info(f"   📌 [{result['id']}] {result['title']} ({result['category']})")

    if count > 0:
        logger.info(f"✅ Index verification passed — {count} results returned")
    else:
        logger.warning("⚠️  No results returned — index may still be building")


def main():
    """Main entry point: create index, embed documents, upload, verify."""
    logger.info("=" * 60)
    logger.info("  PULSE — Knowledge Base Index Setup")
    logger.info(f"  Endpoint: {SEARCH_ENDPOINT}")
    logger.info(f"  Index:    {INDEX_NAME}")
    logger.info("=" * 60)

    credential = DefaultAzureCredential()

    # ── Step 1: Create index ─────────────────────────────────
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=credential,
    )
    create_index(index_client)

    # ── Step 2: Load knowledge base ──────────────────────────
    docs = load_knowledge_base()

    # ── Step 3: Generate embeddings ──────────────────────────
    docs = generate_embeddings(docs)

    # ── Step 4: Upload to index ──────────────────────────────
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=credential,
    )
    upload_documents(search_client, docs)

    # ── Step 5: Verify ───────────────────────────────────────
    verify_index(search_client)

    logger.info("=" * 60)
    logger.info("  ✅ Knowledge base index setup complete!")
    logger.info("  You can now set DEMO_MODE=false in .env")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
