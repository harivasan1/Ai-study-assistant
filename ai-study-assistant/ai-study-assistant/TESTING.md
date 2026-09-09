# TESTING — AI Study Assistant

Manual test cases to verify core functionality. Run the app locally (`streamlit run app.py`) with a valid `OPENAI_API_KEY` unless the test case says otherwise.

| ID | Test Case | Steps | Expected Result |
|---|---|---|---|
| TC01 | Upload valid PDF | Upload a normal, text-based PDF and click "Process Document" | Document is processed; sidebar shows "Ready: <filename>" |
| TC02 | Upload empty/scanned PDF | Upload a PDF with no extractable text (e.g. a scanned image page) | Friendly error: "No readable text was found in this PDF..." |
| TC03 | Ask question related to PDF | After processing, ask a question whose answer is in the document | Grounded answer is returned, with source filename shown |
| TC04 | Ask unrelated question | Ask a question with no relation to the uploaded content | System responds: "This information is not available in the uploaded material." |
| TC05 | Missing API key | Remove `OPENAI_API_KEY` from `.env` and restart the app | Sidebar shows a configuration error; upload/process is disabled |
| TC06 | OpenAI API failure | Temporarily use an invalid API key | Friendly error message shown; no stack trace or key exposed |
| TC07 | Generate summary | Process a document, open the Summary tab, click "Generate Summary" | A structured summary (main topic, concepts, key points) appears, based only on the document |
| TC08 | Generate quiz | Process a document, open the Quiz tab, choose a question count, click "Generate Quiz" | The requested number of MCQs appear, each with 4 options, a correct answer, and an explanation, based only on the document |

## Additional Automated Checks Performed During Development

These were run directly against the service modules (no Streamlit, no live API calls) to validate core logic in isolation:

- `utils.text_utils.chunk_text` — verified a 2000-character input produces correctly sized, overlapping chunks.
- `services.vector_store.VectorStore` — verified `add_documents`, `search`, `save_index`, and `load_index` round-trip correctly and return the expected nearest match.
- `services.pdf_service.extract_text_from_pdf` — verified against a generated sample PDF that known text is correctly extracted.
- `config.settings.load_settings` — verified a `RuntimeError` is raised with a clear message when `OPENAI_API_KEY` is unset.

## Notes

- TC06 requires a live (invalid) key to trigger `AuthenticationError` from the OpenAI SDK — do this deliberately and briefly, then restore the real key.
- For TC02, a quick way to produce a "no text" PDF is exporting a blank page or a pure-image scan to PDF.
