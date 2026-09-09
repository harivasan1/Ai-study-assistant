"""
services/openai_service.py
---------------------------
WHAT:
    The ONLY module that talks directly to the OpenAI API. Every other
    part of the app (RAG, summary, quiz) calls functions here instead
    of importing the `openai` package directly.

WHY:
    Centralizing API calls means:
      - The API key is read from settings in exactly one place.
      - If the SDK, model names, or error-handling strategy change,
        only this file is touched.
      - It is easy to see, audit, and explain every network call the
        app makes to a third party.

HOW:
    Uses the current OpenAI Python SDK (`openai>=1.x`) client pattern:
    `OpenAI(api_key=...)` then `client.chat.completions.create(...)`
    and `client.embeddings.create(...)`.

INPUT:
    Plain strings (prompts, text to embed) and simple parameters.

OUTPUT:
    Plain strings (generated text) or lists of floats (embeddings).
    Never raw SDK exception objects — those are caught and converted
    into a project-specific OpenAIServiceError with a friendly message.
"""

from __future__ import annotations

from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from config.settings import Settings


class OpenAIServiceError(Exception):
    """Raised whenever a call to the OpenAI API fails, with a friendly message."""


_client: OpenAI | None = None
_client_key: str | None = None


def get_client(settings: Settings) -> OpenAI:
    """
    Return a cached OpenAI client, creating it once per API key.

    Caching avoids re-instantiating the client (and re-validating
    config) on every single Streamlit rerun.
    """
    global _client, _client_key

    if _client is None or _client_key != settings.openai_api_key:
        _client = OpenAI(api_key=settings.openai_api_key)
        _client_key = settings.openai_api_key

    return _client


def _handle_call(fn, *args, **kwargs):
    """Run an SDK call and convert known exception types into OpenAIServiceError."""
    try:
        return fn(*args, **kwargs)
    except AuthenticationError as exc:
        raise OpenAIServiceError(
            "Authentication with OpenAI failed. Check that OPENAI_API_KEY is correct."
        ) from exc
    except RateLimitError as exc:
        raise OpenAIServiceError(
            "OpenAI rate limit or quota exceeded. Please wait and try again."
        ) from exc
    except APIConnectionError as exc:
        raise OpenAIServiceError(
            "Could not connect to OpenAI. Check your internet connection."
        ) from exc
    except APIError as exc:
        raise OpenAIServiceError(f"OpenAI API returned an error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise OpenAIServiceError(f"Unexpected error calling OpenAI: {exc}") from exc


def create_embeddings(settings: Settings, texts: list[str]) -> list[list[float]]:
    """
    Create embeddings for a batch of text chunks.

    Args:
        settings: validated app Settings (holds model name + api key).
        texts: list of chunk strings to embed.

    Returns:
        A list of embedding vectors, one per input text, in the same order.
    """
    if not texts:
        return []

    client = get_client(settings)
    response = _handle_call(
        client.embeddings.create,
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def create_query_embedding(settings: Settings, query: str) -> list[float]:
    """Create a single embedding vector for a user question."""
    embeddings = create_embeddings(settings, [query])
    return embeddings[0] if embeddings else []


def generate_answer(settings: Settings, system_prompt: str, user_prompt: str) -> str:
    """
    Generate a grounded answer given a system prompt (instructions +
    retrieved context) and a user prompt (the question).
    """
    client = get_client(settings)
    response = _handle_call(
        client.chat.completions.create,
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,  # low temperature: favor grounded, consistent answers
    )
    return (response.choices[0].message.content or "").strip()


def generate_summary(settings: Settings, system_prompt: str, document_text: str) -> str:
    """Generate a summary of the given document text."""
    client = get_client(settings)
    response = _handle_call(
        client.chat.completions.create,
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": document_text},
        ],
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


def generate_quiz(settings: Settings, system_prompt: str, document_text: str, num_questions: int) -> str:
    """Generate quiz/MCQ questions from the given document text."""
    client = get_client(settings)
    user_prompt = (
        f"Generate exactly {num_questions} multiple-choice questions "
        f"from the following study material:\n\n{document_text}"
    )
    response = _handle_call(
        client.chat.completions.create,
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    return (response.choices[0].message.content or "").strip()
