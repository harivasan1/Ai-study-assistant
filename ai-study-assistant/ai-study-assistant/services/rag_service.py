"""
services/rag_service.py
-------------------------
WHAT:
    The core AI logic of the application. Orchestrates the full RAG
    (Retrieval-Augmented Generation) pipeline, plus the summary and
    quiz generation flows, which are simpler "text in, text out"
    calls that don't need retrieval.

WHY:
    "RAG" solves a real problem: an LLM by itself does not know the
    contents of a student's specific PDF, and if asked about it
    directly, it will either say "I don't have that file" or — worse —
    confidently hallucinate a plausible-sounding but wrong answer.
    RAG fixes this by finding the most relevant pieces of the ACTUAL
    document first, and then instructing the model to answer using
    only that retrieved text.

HOW (question flow):
    Question
      -> embed the question (embedding_service)
      -> search the FAISS vector store for the most similar chunks
      -> build a single "context" string from those chunks
      -> inject that context into the QA system prompt (prompts/qa_prompt.txt)
      -> send system prompt + question to the chat model (openai_service)
      -> return the grounded answer + which sources were used

INPUT:
    A Settings object, a VectorStore holding the processed document,
    and either a question string or raw document text (for
    summary/quiz).

OUTPUT:
    Structured dicts containing the generated text plus supporting
    metadata (sources, chunks used), so the UI can display provenance.
"""

from __future__ import annotations

from pathlib import Path

from config.settings import Settings
from services import embedding_service, openai_service
from services.vector_store import VectorStore

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Read a prompt template from the prompts/ directory."""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _build_context(chunks: list[dict]) -> str:
    """
    Join retrieved chunks into a single context string, labeling each
    with its source filename so the model (and the user) can see
    provenance.
    """
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "unknown")
        text = chunk.get("text", "")
        parts.append(f"[Chunk {i} | Source: {source}]\n{text}")
    return "\n\n".join(parts)


def answer_question(
    settings: Settings,
    vector_store: VectorStore,
    question: str,
) -> dict:
    """
    Run the full RAG pipeline for a single user question.

    Returns:
        {
            "answer": str,
            "sources": list[str],        # unique source filenames used
            "chunks_used": list[dict],   # the raw retrieved chunks
        }
    """
    question = (question or "").strip()
    if not question:
        return {"answer": "Please enter a question.", "sources": [], "chunks_used": []}

    if vector_store.index is None or vector_store.index.ntotal == 0:
        return {
            "answer": "No document has been processed yet. Please upload and process a PDF first.",
            "sources": [],
            "chunks_used": [],
        }

    # 1. Embed the question
    query_embedding = embedding_service.create_query_embedding(settings, question)

    # 2. Search FAISS for the most relevant chunks
    retrieved_chunks = vector_store.search(query_embedding, top_k=settings.top_k)

    if not retrieved_chunks:
        return {
            "answer": "This information is not available in the uploaded material.",
            "sources": [],
            "chunks_used": [],
        }

    # 3. Build context + prompt
    context = _build_context(retrieved_chunks)
    qa_template = _load_prompt("qa_prompt.txt")
    system_prompt = qa_template.format(context=context)

    # 4. Ask the model, grounded in the retrieved context
    answer = openai_service.generate_answer(settings, system_prompt, question)

    sources = sorted({chunk.get("source", "unknown") for chunk in retrieved_chunks})

    return {"answer": answer, "sources": sources, "chunks_used": retrieved_chunks}


def summarize_document(settings: Settings, document_text: str, source_name: str = "document") -> str:
    """
    Summarize a document, using a simple map-reduce strategy for long
    documents so we never silently truncate content or exceed context
    limits.

    - Short documents: summarized directly in one call.
    - Long documents: split into large chunks, each summarized, then
      the partial summaries are combined into one final summary.
    """
    from utils.text_utils import chunk_text

    summary_prompt = _load_prompt("summary_prompt.txt")

    # A generous chunk size for summarization (larger than retrieval
    # chunks, since we're not doing similarity search on these).
    MAP_CHUNK_SIZE = 6000
    MAP_CHUNK_OVERLAP = 200

    if len(document_text) <= MAP_CHUNK_SIZE:
        return openai_service.generate_summary(settings, summary_prompt, document_text)

    # MAP step: summarize each large chunk independently.
    parts = chunk_text(document_text, chunk_size=MAP_CHUNK_SIZE, chunk_overlap=MAP_CHUNK_OVERLAP)
    partial_summaries = []
    for part in parts:
        partial = openai_service.generate_summary(settings, summary_prompt, part)
        partial_summaries.append(partial)

    # REDUCE step: summarize the combined partial summaries into one.
    combined = "\n\n".join(partial_summaries)
    reduce_prompt = (
        summary_prompt
        + f"\n\nNote: this is a combined summary of multiple sections of '{source_name}'. "
        "Merge overlapping points and remove redundancy."
    )
    return openai_service.generate_summary(settings, reduce_prompt, combined)


def generate_quiz(settings: Settings, document_text: str, num_questions: int) -> str:
    """Generate quiz questions grounded strictly in the given document text."""
    quiz_prompt = _load_prompt("quiz_prompt.txt")

    # Cap the amount of source text sent for quiz generation so we stay
    # comfortably within context limits on very large documents.
    MAX_QUIZ_SOURCE_CHARS = 12000
    truncated_text = document_text[:MAX_QUIZ_SOURCE_CHARS]

    return openai_service.generate_quiz(settings, quiz_prompt, truncated_text, num_questions)
