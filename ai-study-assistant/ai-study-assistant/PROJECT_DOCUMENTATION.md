# PROJECT DOCUMENTATION — AI Study Assistant

## 1. Project Introduction

The AI Study Assistant is a Retrieval-Augmented Generation (RAG) web application. A student uploads a PDF; the system extracts, chunks, and embeds its text into a vector database; and the student can then chat with, summarize, or generate a quiz from that specific document.

## 2. Problem Statement

Generic AI chatbots do not know the contents of a student's personal study material, and asking them directly about it either fails outright or produces confident but fabricated ("hallucinated") answers. Students need a tool that is grounded strictly in their own uploaded content.

## 3. Proposed Solution

Combine document ingestion (PDF → text → chunks → embeddings → vector index) with a retrieval step at query time (find the most relevant chunks) and a generation step (ask the LLM to answer using *only* those chunks). This is the RAG pattern, applied to three features: chat Q&A, summarization, and quiz generation.

## 4. Objectives

See README.md §3 — restated here for completeness: reliable ingestion, accurate retrieval, grounded generation, and a clean, secure, deployable implementation.

## 5. Functional Requirements

- FR1: User can upload a PDF file.
- FR2: System extracts text from the PDF.
- FR3: System splits text into overlapping chunks.
- FR4: System generates embeddings for each chunk.
- FR5: System stores embeddings + metadata in a vector index.
- FR6: User can ask a question; system retrieves relevant chunks and returns a grounded answer.
- FR7: User can request a summary of the document.
- FR8: User can request a configurable number of quiz questions.
- FR9: System clearly states when an answer is not present in the material.

## 6. Non-Functional Requirements

- NFR1: The OpenAI API key must never appear in source code or the browser.
- NFR2: Errors must be shown to the user in friendly language, without stack traces.
- NFR3: The codebase must be modular (one responsibility per file).
- NFR4: The app must be deployable on Render with no code changes.

## 7. System Architecture

```
┌──────────────────┐
│     Student      │
└────────┬─────────┘
         ▼
┌──────────────────┐
│   Streamlit UI    │   app.py
└────────┬─────────┘
         │
 ┌───────┴────────┐
 ▼                 ▼
Upload PDF     Ask Question
 │                 │
 ▼                 ▼
pdf_service.py   embedding_service.py
 │                 │
 ▼                 ▼
Text Chunking    Query Vector
 │                 │
 ▼                 ▼
Embeddings       FAISS Search
 │                 │
 ▼                 ▼
vector_store.py  Relevant Chunks
 │                 │
 └───────┬─────────┘
         ▼
   rag_service.py
         ▼
  openai_service.py
         ▼
   Grounded Answer
```

## 8. Data Flow

**Ingestion (once per uploaded document):**
PDF bytes → `pdf_service.extract_text_from_pdf` → raw text → `text_utils.clean_text` → cleaned text → `text_utils.chunk_text` → list of chunks → `embedding_service.create_embeddings` → list of vectors → `VectorStore.add_documents` → FAISS index + metadata list.

**Query (once per question):**
Question string → `embedding_service.create_query_embedding` → query vector → `VectorStore.search` → top-K metadata dicts (each with `text`, `source`, `chunk_id`, `score`) → `rag_service._build_context` → context string → injected into `prompts/qa_prompt.txt` → `openai_service.generate_answer` → answer string.

## 9. RAG Architecture

RAG stands for **Retrieval-Augmented Generation**: instead of asking an LLM to answer purely from what it memorized during training, we first *retrieve* relevant real text from a trusted source (the student's own PDF), then *augment* the model's prompt with that text, so *generation* is grounded in facts we can point to. This project implements RAG explicitly in `services/rag_service.answer_question`.

## 10. File-by-File Explanation

| File | Responsibility | Input | Output |
|---|---|---|---|
| `app.py` | Streamlit UI and session state | User interaction | Rendered UI |
| `config/settings.py` | Load & validate configuration | Environment variables | `Settings` object |
| `services/pdf_service.py` | Extract text from PDF | Uploaded file | Cleaned text string |
| `utils/text_utils.py` | Clean and chunk text | Raw/cleaned text | List of chunk strings |
| `services/embedding_service.py` | Text → vector | Chunk(s) or question | Embedding vector(s) |
| `services/vector_store.py` | Store & search vectors | Embeddings + metadata | Ranked similar chunks |
| `services/rag_service.py` | Orchestrate RAG / summary / quiz | Question or document text | Answer / summary / quiz text |
| `services/openai_service.py` | Talk to OpenAI API | Prompts | Generated text or embeddings |
| `prompts/qa_prompt.txt` | QA grounding instructions | — | System prompt template |
| `prompts/summary_prompt.txt` | Summarization instructions | — | System prompt template |
| `prompts/quiz_prompt.txt` | Quiz generation instructions | — | System prompt template |

## 11. PDF Processing

`services/pdf_service.py` uses `pypdf.PdfReader` to open the file and iterate pages, calling `page.extract_text()` on each. Pages that fail to extract (e.g. corrupted) are skipped rather than aborting the whole document. Encrypted PDFs are given one empty-password decrypt attempt (many "protected" PDFs have no real password) before raising a friendly error.

## 12. Text Chunking

**WHAT:** Splitting a long document into smaller overlapping pieces.
**WHY:** Embedding models and LLM context windows have limits, and semantic search is more accurate on small, focused pieces than on one giant blurred-together vector.
**HOW:** `utils/text_utils.chunk_text` walks the text in windows of `CHUNK_SIZE` characters, advancing by `CHUNK_SIZE - CHUNK_OVERLAP` each step so consecutive chunks share `CHUNK_OVERLAP` characters — preventing an idea at a chunk boundary from being cut in half and losing meaning.

## 13. Embeddings

**WHAT:** An embedding is a list of floating-point numbers (a vector) that represents the *meaning* of a piece of text.
**WHY:** Texts with similar meaning produce vectors that are numerically close together, even if they use completely different words — this is what makes semantic (meaning-based) search possible, unlike simple keyword matching.
**HOW:** `services/embedding_service.py` calls `openai_service.create_embeddings`, which uses `client.embeddings.create(model=..., input=texts)` from the OpenAI SDK.
**REAL-WORLD USE:** Search engines, recommendation systems, plagiarism detection, and — as here — document Q&A all rely on embeddings.

## 14. Vector Database

**WHAT:** A specialized store optimized for finding the "nearest" vectors to a given query vector.
**WHY:** A normal database can filter and sort exact values, but cannot efficiently answer "which of these 500 vectors is most *similar* to this one?" — that requires distance calculations across many dimensions, which is what FAISS is built for.
**HOW:** `services/vector_store.py` wraps `faiss.IndexFlatL2`, an exact L2 (Euclidean)-distance index. It keeps a parallel Python list (`metadata`) so each vector's position in the index always corresponds to the same position in the metadata list.

## 15. Semantic Search

**WHAT:** Finding text that is *conceptually* related to a query, not just textually identical.
**WHY:** A student might ask "What causes overfitting?" even if the document says "a model that performs poorly on unseen data due to memorizing training noise" — no shared keywords, but the same meaning.
**HOW:** `VectorStore.search()` embeds the query the same way document chunks were embedded, then asks FAISS for the `top_k` nearest vectors by L2 distance.

## 16. Prompt Engineering

**WHAT:** Deliberately designing the instructions given to an LLM to control its behavior.
**WHY:** Without explicit grounding instructions, an LLM will happily guess an answer that sounds plausible but is wrong. The QA prompt (`prompts/qa_prompt.txt`) explicitly tells the model to answer *only* from the supplied context and to say clearly when something isn't covered.
**HOW:** Prompts are stored as `.txt` files and loaded at runtime (`rag_service._load_prompt`), keeping them out of the Python code and easy to iterate on without touching logic.

## 17. OpenAI Integration

**WHAT:** The application calls two OpenAI capabilities: embeddings (`text-embedding-3-small` by default) and chat completions (`gpt-4o-mini` by default).
**WHY these defaults:** Both are fast, inexpensive, and more than sufficient for a single-document study use case.
**HOW:** All calls are centralized in `services/openai_service.py`, which wraps SDK exceptions (`AuthenticationError`, `RateLimitError`, `APIConnectionError`, `APIError`) into a single friendly `OpenAIServiceError`.

## 18. Chatbot Logic

The Streamlit "Chat" tab (`app.py`) keeps a `chat_history` list in `st.session_state`. Each user message triggers `rag_service.answer_question`, and both the question and the grounded answer (plus source filenames) are appended to history so the conversation persists across Streamlit reruns within a session.

## 19. Summary Logic

`rag_service.summarize_document` sends the document text to the model with `prompts/summary_prompt.txt` as the system prompt. For documents longer than ~6000 characters, it uses a **map-reduce** strategy: split into large chunks, summarize each chunk independently ("map"), then summarize the combined partial summaries into one final summary ("reduce") — this avoids exceeding model context limits and avoids silently truncating content.

## 20. Quiz Logic

`rag_service.generate_quiz` sends (a capped amount of) document text plus the requested question count to the model with `prompts/quiz_prompt.txt`, which enforces a strict output format: 4 lettered options, a stated correct answer, and a one-sentence explanation per question.

## 21. Security

- API key read only from environment variables (`config/settings.py`), never hard-coded.
- `.env` is git-ignored; `.env.example` documents required variables without real values.
- `render.yaml` marks `OPENAI_API_KEY` as `sync: false` so it must be entered directly in the Render dashboard.
- The key never crosses into frontend/browser code — Streamlit callbacks run server-side, and only `services/openai_service.py` ever touches the key.

## 22. Error Handling

Every user-facing action in `app.py` is wrapped in `try/except`, converting exceptions into `st.error(...)` messages. Domain-specific exceptions (`PdfExtractionError`, `OpenAIServiceError`) carry friendly messages by design, so the UI never leaks stack traces or the API key.

## 23. Deployment

See README.md §14. In short: Render builds with `pip install -r requirements.txt` and starts with `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`, with `OPENAI_API_KEY` set as a dashboard environment variable.

## 24. Testing

See `TESTING.md` for the full test case list (TC01–TC08) covering upload, extraction failures, grounded and unrelated questions, missing API key, API failures, summary, and quiz generation.

## 25. Limitations

See README.md §16.

## 26. Future Scope

See README.md §17.

## 27. Conclusion

This documentation, together with `README.md` and `TESTING.md`, covers the AI Study Assistant's architecture, data flow, RAG design, security posture, and deployment procedure end to end, mapping each implementation choice back to the underlying AI/software-engineering concept it demonstrates.
