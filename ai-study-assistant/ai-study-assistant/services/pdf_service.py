"""
services/pdf_service.py
------------------------
WHAT:
    Extracts raw text from an uploaded PDF file.

WHY:
    Everything downstream (chunking, embeddings, retrieval) operates on
    plain text. This module is the single boundary between "PDF bytes"
    and "text the rest of the app understands" — if PDF parsing ever
    needs to change (e.g. add OCR for scanned PDFs), only this file
    changes.

HOW:
    Uses pypdf to open the PDF page by page and concatenate extracted
    text. Empty/unreadable pages (e.g. pure-image scans with no text
    layer) are skipped rather than crashing the whole extraction.

INPUT:
    A file-like object (what Streamlit's file_uploader returns) or a
    filesystem path.

OUTPUT:
    A single string containing the concatenated, cleaned text of the
    document, or an empty string if nothing could be extracted.
"""

from __future__ import annotations

from typing import BinaryIO, Union

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from utils.text_utils import clean_text

PdfSource = Union[str, BinaryIO]


class PdfExtractionError(Exception):
    """Raised when a PDF cannot be read at all (corrupt/not a PDF)."""


def extract_text_from_pdf(source: PdfSource) -> str:
    """
    Extract and clean text from a PDF.

    Args:
        source: a path to a PDF file, or a file-like object such as
            the one returned by st.file_uploader.

    Returns:
        Cleaned, concatenated text from all readable pages.

    Raises:
        PdfExtractionError: if the file cannot be parsed as a PDF at all.
    """
    try:
        reader = PdfReader(source)
    except PdfReadError as exc:
        raise PdfExtractionError(f"Could not read this file as a PDF: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - we deliberately convert any failure
        raise PdfExtractionError(f"Unexpected error opening PDF: {exc}") from exc

    if reader.is_encrypted:
        # Try an empty-password decrypt; many "encrypted" PDFs just have
        # restrictions with no real password. If it fails, surface a clear error.
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001
            raise PdfExtractionError(
                "This PDF is password-protected and cannot be read."
            ) from exc

    page_texts: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            # One bad page shouldn't kill extraction for the whole document.
            page_text = ""

        page_text = page_text.strip()
        if page_text:
            page_texts.append(page_text)

    full_text = "\n\n".join(page_texts)
    return clean_text(full_text)
