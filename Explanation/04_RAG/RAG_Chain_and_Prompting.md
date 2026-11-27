# RAG Chain and Prompting

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Source: [`ai/rag/rag_chain.py`](../../ai/rag/rag_chain.py), UI in [`ai/rag/chatbot.py`](../../ai/rag/chatbot.py).

## 1. The prompt (verbatim)

```python
RAG_PROMPT_TEMPLATE = """You are a helpful assistant for the Personal Finance Tracker application.
Answer the user's question using ONLY the information provided in the context below.
If the context does not contain enough information to answer the question, say exactly:
"{no_info}"

Do NOT make up information. Do NOT invent features, buttons, endpoints or numbers.
Do NOT answer questions about topics outside the Finance Tracker application (for example the stock market or recipes);
for those, give the sentence above.

Context:
{context}

Question: {question}

Answer:"""
```

`{no_info}` is a `partial_variable` filled with `NO_INFO = "I don't have information about that in the Finance Tracker user manual."` so the refusal sentence is defined once. Input variables: `context`, `question`.

Prompt-design points: (1) explicit grounding instruction; (2) an **exact** refusal sentence (easy to test and to recognise in the UI); (3) negative instructions against invention; (4) explicit out-of-scope examples; (5) the question comes after the context.

## 2. Context injection

```python
context = "\n\n".join(f"[{d.metadata.get('section', 'Manual')}]\n{d.page_content}" for d in docs)
```

Each retrieved chunk is prefixed with its manual section in square brackets so the model can see where the text came from. The 4 chunks (≤ 512 chars each) plus the template stay far below any model context limit.

## 3. The chain object

```python
class RagChain:
    def __init__(self, retriever, llm):
        self.retriever = retriever
        self.prompt = PromptTemplate(template=RAG_PROMPT_TEMPLATE, input_variables=["context","question"],
                                     partial_variables={"no_info": NO_INFO})
        self.generation = self.prompt | llm | RunnableLambda(message_text)     # LCEL pipeline

    def retrieve(self, question): ...   # span rag.retrieve
    def generate(self, question, docs): # span rag.generate
        return self.generation.invoke({"context": context, "question": question}).strip()
    def invoke(self, question):
        docs = self.retrieve(question)
        if not docs: return {"answer": NO_INFO, "docs": []}
        return {"answer": self.generate(question, docs), "docs": docs}
```

* **LCEL** (`prompt | llm | parser`) composes runnables: the dict feeds the prompt template → rendered prompt goes to the chat model → the model's `AIMessage` is converted to a plain string by `message_text`.
* `message_text` handles Gemini 3 responses whose `content` may be a **list of blocks** (text, thinking, signature) — only `type == "text"` blocks are concatenated (`test_gen_handles_gemini_content_blocks`).
* Retrieval and generation are separate methods so the sources are available even if you only want retrieval, and so the LLM is skipped when nothing is retrieved.

## 4. `ask_question` (public entry point)

```python
@traceable_if_enabled(name="finance_rag_query", project_name="AI-Readiness-POC-02-P2", process_inputs=lambda i: {"question": i.get("question")})
def ask_question(question, chain) -> dict
```

Returns `{"answer": str, "sources": [snippet…], "source_details": [{"section","snippet"}…]}` (plus `"error": "<ExceptionName>"` on failure). Flow: strip → empty guard → `chain.invoke` in `try/except` → build details → log `rag_query_completed` (`question[:80]`, `answer_length`, `source_count`, `duration_ms`).

Error handling: **any** exception → logs `llm_call_failed` (`error_type`, `question[:80]`) and returns `LLM_UNAVAILABLE = "Sorry, I couldn't reach the AI service just now. Please try again in a moment."` — the UI never shows a stack trace. Retries are delegated to the Gemini client (`max_retries=2`, `timeout=60` s; see [Gemini_Integration](Gemini_Integration.md)); the RAG code adds none.

## 5. Streamlit chatbot (`chatbot.py`)

| Piece | Behaviour |
|---|---|
| Launch | `streamlit run ai/rag/chatbot.py --server.port 8501` |
| Modes | sidebar radio: **Manual Q&A (RAG)** (`MODE_FAQ`) and **My finances (live data)** (`MODE_AGENT`, the Phase 3 agent) |
| Chain loading | `@st.cache_resource def load_chain(): return build_rag_chain()`; failures show `st.error` and `st.stop()` (both modes need the chain — the agent uses it as a tool) |
| Sample questions | `SAMPLE_QUESTIONS` buttons ("How do I set a monthly budget?", "What account types are supported?", "What happens when I exceed my budget?", "How is the savings rate calculated?", "What transaction categories are available?", "How do I pay my credit card bill?") |
| History | each mode keeps its own list in `st.session_state` (`messages` / `agent_messages`), re-rendered each run with answer and sources/tool calls; "Clear conversation" resets it |
| **Memory in FAQ mode** | **None used by the model.** `ask_question(question, chain)` receives only the current question; history is display-only. Follow-ups like "and what about transport?" lose context. The agent mode *does* pass `chat_history` |
| Sources | `render_sources` expander under each assistant answer |

## 6. Why this is "grounded" and where it can still fail

* **Grounded**: the only knowledge injected is the retrieved manual text; the prompt forbids outside knowledge; sources are visible.
* **Can still fail**: (a) retrieval misses the relevant chunk; (b) the model ignores the instruction (no automated faithfulness check exists); (c) the manual itself is out of date versus the code; (d) multi-turn context is not used in FAQ mode. The manual's content was written to match the implemented behaviour, but there is no automated sync between manual and code.

## 7. Tests (mock tier)

`test_gen_answer_is_non_empty_string_and_prompt_is_grounded` (prompt contains context and the ONLY/refuse rules), `test_gen_no_retrieved_context_declines_without_calling_llm`, `test_gen_llm_failure_is_handled_and_logged`, `test_missing_api_key_gives_clear_error`, `test_empty_knowledge_base_gives_clear_error`, `test_obs_03_structured_log_fields`, `test_obs_02_required_otel_spans_present`, `test_obs_04_source_documents_returned`, `test_chatbot_ui_shows_history_answer_and_sources`, `test_chatbot_ui_shows_clear_error_without_api_key` — using `ScriptedChatModel` + `HashEmbeddings` (no network). Live equivalents in `tests/phase2/test_rag_live.py` are skipped without `GOOGLE_API_KEY`.
