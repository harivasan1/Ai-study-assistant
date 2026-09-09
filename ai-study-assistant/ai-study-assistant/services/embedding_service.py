"""
services/embedding_service.py
------------------------------
WHAT:
    Converts text (document chunks or a user's question) into
    embedding vectors, using openai_service as the transport layer.

WHY:
    An "embedding" is a list of numbers (e.g. 1536 floats) that
    represents the MEANING of a piece of text in a high-dimensional
    space. Texts with similar meaning end up with vectors that are
    close together, even if they use completely different words. This
    is what makes semantic search possible: instead of matching exact
    keywords, we can compare meaning.

    Keeping this as its own module (separate from openai_service) means
    if we ever want a different embedding provider or a local
    embedding model, only this file changes — vector_store.py and
    rag_service.py wouldn't need to know or care.

HOW:
    Thin wrapper functions around openai_service's embedding calls.
    Kept deliberately free of any FAISS/vector-store logic — this
    module's only job is "text in, vector(s) out".

INPUT:
    Cleaned document chunks or a single user question string.

OUTPUT:
    NumPy-ready lists of floats representing the semantic embedding.
"""

from __future__ import annotations

from config.settings import Settings
from services import openai_service


def create_embeddings(settings: Settings, chunks: list[str]) -> list[list[float]]:
    """
    Create one embedding vector per document chunk.

    This is called once per document during ingestion (upload +
    process), not on every question, so it's fine for it to be
    slightly slower for large documents — it only runs once.
    """
    return openai_service.create_embeddings(settings, chunks)


def create_query_embedding(settings: Settings, question: str) -> list[float]:
    """
    Create a single embedding vector for the user's current question.

    Called once per question, right before searching the FAISS index.
    """
    return openai_service.create_query_embedding(settings, question)
