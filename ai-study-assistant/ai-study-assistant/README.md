# AI Study Assistant

An AI-powered study assistant that lets a student upload PDF study material and then ask questions, get a summary, or generate a practice quiz — all grounded in the actual content of that document using Retrieval-Augmented Generation (RAG).

---

## 1. Project Overview

This project is a web application built with Streamlit and the OpenAI API. A student uploads a PDF, the app extracts and indexes its content using embeddings and a FAISS vector database, and the student can then interact with the material through a chat interface, a one-click summary, or an auto-generated multiple-choice quiz.

## 2. Problem Statement

Students accumulate large amounts of PDF study material (notes, textbooks, slides) but reviewing it manually is slow, and generic AI chatbots cannot answer questions about a *specific* document, often producing generic or hallucinated answers. There is a need for a tool that answers questions strictly using a student's own uploaded material and clearly says when something isn't covered.

## 3. Objectives

- Allow PDF upload and reliable text extraction.
- Split documents into retrievable chunks.
- Generate and store semantic embeddings for those chunks.
- Retrieve the most relevant chunks for a given question using vector similarity search.
- Generate answers grounded in retrieved context (RAG), avoiding hallucination.
- Generate document summaries and quizzes from the same material.
- Deploy the finished app publicly on Render.

## 4. Features

- 📄 PDF upload and text extraction
- ✂️ Configurable text chunking with overlap
- 🧠 OpenAI embeddings for semantic search
- 🔍 FAISS-based vector similarity search
- 💬 RAG-based chat that answers only from the uploaded document
- 📝 Document summarization (with map-reduce for long documents)
- ❓ Auto-generated multiple-choice quizzes with answers and explanations
- 🔒 API key kept server-side only, never exposed to the browser
- ☁️ Render-ready deployment configuration

## 5. Technology Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| LLM + Embeddings | OpenAI API |
| PDF parsing | pypdf |
| Vector database | FAISS (faiss-cpu) |
| Numerical processing | NumPy |
| Config / secrets | python-dotenv |
| Hosting | Render |
| Version control | Git + GitHub |

## 6. System Architecture

```
USER
 ↓
STREAMLIT UI (app.py)
 ↓
PDF SERVICE (text extraction)
 ↓
TEXT CHUNKING (utils/text_utils.py)
 ↓
EMBEDDING SERVICE (services/embedding_service.py)
 ↓
FAISS VECTOR STORE (services/vector_store.py)
 ↓
RAG SERVICE (services/rag_service.py)
 ↓
OPENAI SERVICE (services/openai_service.py)
 ↓
GROUNDED ANSWER / SUMMARY / QUIZ
```

## 7. Project Structure

```
ai-study-assistant/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── PROJECT_DOCUMENTATION.md
├── TESTING.md
├── render.yaml
├── config/
│   ├── __init__.py
│   └── settings.py
├── services/
│   ├── __init__.py
│   ├── openai_service.py
│   ├── pdf_service.py
│   ├── embedding_service.py
│   ├── vector_store.py
│   └── rag_service.py
├── prompts/
│   ├── qa_prompt.txt
│   ├── summary_prompt.txt
│   └── quiz_prompt.txt
├── utils/
│   ├── __init__.py
│   └── text_utils.py
├── data/
│   └── documents/
└── vectorstore/
```

## 8. How Each File Works

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI, session state, wires user actions to services |
| `config/settings.py` | Loads and validates environment variables |
| `services/pdf_service.py` | Extracts text from uploaded PDFs |
| `utils/text_utils.py` | Cleans text and splits it into overlapping chunks |
| `services/embedding_service.py` | Converts text into embedding vectors |
| `services/vector_store.py` | FAISS index + metadata (the vector database) |
| `services/rag_service.py` | Orchestrates retrieval + generation for chat, summary, quiz |
| `services/openai_service.py` | The only module that calls the OpenAI API directly |
| `prompts/*.txt` | Externalized prompt templates |

See `PROJECT_DOCUMENTATION.md` for a deeper, file-by-file breakdown.

## 9. RAG Workflow

```
Question
   ↓
Embedding (embedding_service)
   ↓
FAISS Search (vector_store)
   ↓
Top-K Relevant Chunks
   ↓
Context Builder (rag_service)
   ↓
QA Prompt (prompts/qa_prompt.txt)
   ↓
OpenAI Chat Completion (openai_service)
   ↓
Grounded Answer + Source Filenames
```

## 10. Installation

```bash
git clone https://github.com/<your-username>/ai-study-assistant.git
cd ai-study-assistant
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 11. Environment Variables

Copy `.env.example` to `.env` and fill in your key:

```
OPENAI_API_KEY=your_api_key_here
CHUNK_SIZE=800
CHUNK_OVERLAP=120
TOP_K=4
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o-mini
```

`.env` is git-ignored and must never be committed.

## 12. Running Locally

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## 13. GitHub Setup

```bash
git init
git add .
git commit -m "Initial commit: AI Study Assistant"
git branch -M main
git remote add origin https://github.com/<your-username>/ai-study-assistant.git
git push -u origin main
```

Double-check `.env` is **not** in the commit (`.gitignore` already excludes it).

## 14. Render Deployment

1. Push the repository to GitHub.
2. In Render, click **New → Web Service** and connect the repo.
3. Render will detect `render.yaml`. If not, set manually:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
4. In the Render dashboard, add an environment variable:
   - `OPENAI_API_KEY` = your real key (set here only, never in code or `render.yaml`).
5. Deploy. Render assigns a public URL once the build succeeds.

## 15. Security

- The API key lives only in environment variables (`.env` locally, Render dashboard in production) — never in source code.
- `.env` is excluded via `.gitignore`.
- `render.yaml` references `OPENAI_API_KEY` with `sync: false`, meaning Render will *not* store or expose a value from the repo — it must be entered manually in the dashboard.
- Streamlit UI code never receives or displays the API key; all OpenAI calls happen server-side in `services/openai_service.py`.
- Errors shown to the user are friendly messages, not raw stack traces or secrets.

## 16. Limitations

- Scanned/image-only PDFs with no text layer cannot be read (no OCR included).
- FAISS `IndexFlatL2` performs an exact search — fine for single-document study use, but not optimized for very large multi-document corpora.
- No persistent multi-user storage; each session's document lives in memory (or on-disk under `vectorstore/` if explicitly saved).
- Quiz generation truncates extremely long documents to stay within context limits.

## 17. Future Enhancements

- OCR support for scanned documents.
- Multi-document libraries with persistent, per-user vector stores.
- Streaming responses in the chat UI.
- Support for additional file types (DOCX, PPTX).
- User authentication and saved chat history across sessions.

## 18. Academic Relevance

This project demonstrates applied concepts in AI application development: LLM integration, prompt engineering, vector embeddings, semantic search, and Retrieval-Augmented Generation, combined with standard software engineering practice (modular architecture, secret management, testing, deployment).

## 19. Practical Mapping

| Syllabus Topic | Project Component |
|---|---|
| OpenAI API | `services/openai_service.py` |
| Prompt Engineering | `prompts/*.txt` |
| LLM | Chat completion calls |
| Embeddings | `services/embedding_service.py` |
| Vector Database | FAISS (`services/vector_store.py`) |
| Semantic Search | `VectorStore.search()` |
| RAG | `services/rag_service.py` |
| AI Chatbot | Streamlit chat tab |
| Responsible AI | Grounding + "not available" fallback in QA prompt |
| Security | `config/settings.py`, `.gitignore`, `render.yaml` |
| Deployment | Render (`render.yaml`) |
| GitHub | Version control workflow, this README |

## 20. Conclusion

The AI Study Assistant is a complete, working demonstration of a production-style RAG application: it ingests real documents, builds a genuine vector index, retrieves relevant context, and generates grounded answers, summaries, and quizzes — while following sound security and deployment practices suitable for a public GitHub repository and a live Render deployment.

For a deeper technical walkthrough, see `PROJECT_DOCUMENTATION.md`. For test cases, see `TESTING.md`.
