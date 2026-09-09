"""
utils/text_utils.py
--------------------
WHAT:
    Pure text-processing helpers: whitespace cleanup and chunking.
    "Pure" means these functions take a string in and return a string
    or list out — no I/O, no API calls, no Streamlit. That makes them
    trivial to unit test.

WHY (chunking, specifically):
    LLMs and embedding models have limited context windows, and
    semantic search works better on small, focused pieces of text than
    on one giant document. If we embedded a whole 20-page PDF as a
    single vector, the vector would be a "blurry average" of everything
    in the document, and retrieval would be inaccurate. Splitting text
    into overlapping chunks means:
      - Each chunk is small enough to embed meaningfully.
      - Overlap prevents an idea that spans a chunk boundary from being
        cut in half and losing its meaning.

INPUT:
    Raw or lightly-cleaned text extracted from a PDF.

OUTPUT:
    A list of chunk strings ready to be embedded.
"""

from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """
    Normalize whitespace and drop obviously empty content.

    PDF extraction often produces irregular spacing, repeated blank
    lines, and stray control characters. This function does not try to
    "fix" the content (we must not alter meaning), it only normalizes
    formatting so downstream chunking works on tidy text.
    """
    if not text:
        return ""

    # Collapse Windows/Mac line endings to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse 3+ blank lines into a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse runs of spaces/tabs into a single space (but keep newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 120) -> list[str]:
    """
    Split text into overlapping chunks measured in characters.

    Character-based chunking (rather than word or token-based) keeps
    the implementation dependency-free and easy for a student to
    reason about, while still producing chunks of a predictable size.

    Args:
        text: cleaned document text.
        chunk_size: target number of characters per chunk.
        chunk_overlap: number of characters repeated between consecutive
            chunks, so context isn't lost at chunk boundaries.

    Returns:
        List of non-empty chunk strings. Returns an empty list if the
        input text is empty.
    """
    text = clean_text(text)
    if not text:
        return []

    if chunk_overlap >= chunk_size:
        # Guard against a misconfiguration that would cause an infinite loop.
        chunk_overlap = max(0, chunk_size // 4)

    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == text_length:
            break

        # Move forward, re-using the last `chunk_overlap` characters
        # as the start of the next chunk.
        start = end - chunk_overlap

    return chunks
