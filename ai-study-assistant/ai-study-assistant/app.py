"""
app.py
------
WHAT:
    The Streamlit entry point. Owns the UI only: layout, widgets,
    session state, and wiring user actions to service-layer functions.

WHY it stays "thin":
    Business logic (PDF parsing, embeddings, FAISS, prompting OpenAI)
    lives in services/. That separation means the core AI logic can be
    tested or reused (e.g. from a CLI script or a different frontend)
    without dragging Streamlit along, and this file stays readable as
    "what happens when the user clicks X".

RUN LOCALLY:
    streamlit run app.py

RUN ON RENDER:
    streamlit run app.py --server.port $PORT --server.address 0.0.0.0
"""

from __future__ import annotations

import streamlit as st

from config.settings import load_settings
from services import rag_service
from services.pdf_service import PdfExtractionError, extract_text_from_pdf
from services.vector_store import VectorStore
from services import embedding_service
from utils.text_utils import chunk_text

st.set_page_config(page_title="AI Study Assistant", page_icon="📚", layout="wide")


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
def init_session_state() -> None:
    defaults = {
        "vector_store": VectorStore(),
        "document_processed": False,
        "document_text": "",
        "document_name": "",
        "chat_history": [],   # list of {"role": "user"/"assistant", "content": str, "sources": list}
        "summary": "",
        "quiz": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ---------------------------------------------------------------------------
# Settings (loaded once, with a friendly error if the API key is missing)
# ---------------------------------------------------------------------------
try:
    settings = load_settings()
    settings_error = None
except RuntimeError as exc:
    settings = None
    settings_error = str(exc)


# ---------------------------------------------------------------------------
# Sidebar: upload + processing + status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📚 AI Study Assistant")

    if settings_error:
        st.error(settings_error)
        st.caption("Set OPENAI_API_KEY in a .env file (see .env.example) and restart the app.")

    st.subheader("Upload PDF")
    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

    process_clicked = st.button("Process Document", disabled=(uploaded_file is None or settings is None))

    if process_clicked and uploaded_file is not None and settings is not None:
        with st.spinner("Extracting text..."):
            try:
                raw_text = extract_text_from_pdf(uploaded_file)
            except PdfExtractionError as exc:
                st.error(f"Could not process this PDF: {exc}")
                raw_text = ""

        if not raw_text:
            st.error(
                "No readable text was found in this PDF. It may be a scanned "
                "image without a text layer, or an empty file."
            )
        else:
            with st.spinner("Splitting text into chunks..."):
                chunks = chunk_text(
                    raw_text,
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                )

            if not chunks:
                st.error("The document did not produce any usable text chunks.")
            else:
                try:
                    with st.spinner(f"Generating embeddings for {len(chunks)} chunks..."):
                        embeddings = embedding_service.create_embeddings(settings, chunks)

                    metadata = [
                        {"text": chunk, "source": uploaded_file.name, "chunk_id": i}
                        for i, chunk in enumerate(chunks)
                    ]

                    store = VectorStore()
                    store.add_documents(embeddings, metadata)

                    st.session_state.vector_store = store
                    st.session_state.document_processed = True
                    st.session_state.document_text = raw_text
                    st.session_state.document_name = uploaded_file.name
                    # Reset downstream state tied to the old document
                    st.session_state.chat_history = []
                    st.session_state.summary = ""
                    st.session_state.quiz = ""

                    st.success(f"Processed '{uploaded_file.name}' into {len(chunks)} chunks.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed to process document: {exc}")

    st.subheader("Document Status")
    if st.session_state.document_processed:
        st.success(f"Ready: {st.session_state.document_name}")
    else:
        st.info("Not processed")

    st.subheader("Features")
    st.caption("💬 Ask questions about your document")
    st.caption("📝 Generate a summary")
    st.caption("❓ Generate a practice quiz")


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.header("AI Study Assistant")

if settings is None:
    st.warning("Configure your OpenAI API key in the sidebar instructions to get started.")
    st.stop()

tab_chat, tab_summary, tab_quiz = st.tabs(["💬 Chat", "📝 Summary", "❓ Quiz"])

# --- Chat tab ---------------------------------------------------------------
with tab_chat:
    if not st.session_state.document_processed:
        st.info("Upload and process a PDF from the sidebar to start asking questions.")
    else:
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                if message.get("sources"):
                    st.caption("Source(s): " + ", ".join(message["sources"]))

        question = st.chat_input("Ask a question about your document...")
        if question:
            st.session_state.chat_history.append({"role": "user", "content": question, "sources": []})
            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        result = rag_service.answer_question(
                            settings, st.session_state.vector_store, question
                        )
                        st.write(result["answer"])
                        if result["sources"]:
                            st.caption("Source(s): " + ", ".join(result["sources"]))
                        st.session_state.chat_history.append(
                            {
                                "role": "assistant",
                                "content": result["answer"],
                                "sources": result["sources"],
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        error_msg = f"Sorry, something went wrong answering that question: {exc}"
                        st.error(error_msg)
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": error_msg, "sources": []}
                        )

# --- Summary tab --------------------------------------------------------------
with tab_summary:
    if not st.session_state.document_processed:
        st.info("Upload and process a PDF from the sidebar to generate a summary.")
    else:
        if st.button("Generate Summary"):
            with st.spinner("Summarizing document..."):
                try:
                    st.session_state.summary = rag_service.summarize_document(
                        settings,
                        st.session_state.document_text,
                        st.session_state.document_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed to generate summary: {exc}")

        if st.session_state.summary:
            st.markdown(st.session_state.summary)

# --- Quiz tab -------------------------------------------------------------
with tab_quiz:
    if not st.session_state.document_processed:
        st.info("Upload and process a PDF from the sidebar to generate a quiz.")
    else:
        num_questions = st.slider("Number of questions", min_value=3, max_value=10, value=5)
        if st.button("Generate Quiz"):
            with st.spinner("Generating quiz..."):
                try:
                    st.session_state.quiz = rag_service.generate_quiz(
                        settings, st.session_state.document_text, num_questions
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed to generate quiz: {exc}")

        if st.session_state.quiz:
            st.markdown(st.session_state.quiz)
