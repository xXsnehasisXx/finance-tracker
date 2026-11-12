"""Phase 2 RAG chain: retrieve (top-4 from ChromaDB) -> grounded prompt -> Gemini. Returns the answer with its sources.

Built with LCEL (prompt | llm | text) rather than the removed RetrievalQA helper; behaviour matches the POC:
answers only from the manual and declines anything else.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from common.observability import configure_logging, get_logger, span, traceable_if_enabled  # noqa: E402

PHASE = 2
configure_logging(PHASE)
logger = get_logger("rag.chain", PHASE)

CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")))
COLLECTION_NAME = "finance_manual"
TOP_K = 4
NO_INFO = "I don't have information about that in the Finance Tracker user manual."
EMPTY_QUESTION = "Please type a question about the Finance Tracker application."
LLM_UNAVAILABLE = "Sorry, I couldn't reach the AI service just now. Please try again in a moment."

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


class RagChain:
    def __init__(self, retriever, llm):
        from langchain_core.output_parsers import StrOutputParser  # noqa: F401
        from langchain_core.prompts import PromptTemplate
        from langchain_core.runnables import RunnableLambda

        from common.llm import message_text

        self.retriever = retriever
        self.prompt = PromptTemplate(template=RAG_PROMPT_TEMPLATE, input_variables=["context", "question"], partial_variables={"no_info": NO_INFO})
        self.generation = self.prompt | llm | RunnableLambda(message_text)

    def retrieve(self, question: str):
        with span("rag.retrieve", **{"rag.query": question[:100], "rag.top_k": TOP_K}) as sp:
            docs = self.retriever.invoke(question)
            sp.set_attribute("rag.retrieved_count", len(docs))
        return docs

    def generate(self, question: str, docs) -> str:
        context = "\n\n".join(f"[{d.metadata.get('section', 'Manual')}]\n{d.page_content}" for d in docs)
        with span("rag.generate", **{"rag.context_chunks": len(docs)}) as sp:
            answer = self.generation.invoke({"context": context, "question": question}).strip()
            sp.set_attribute("answer_length", len(answer))
        return answer

    def invoke(self, question: str) -> dict:
        docs = self.retrieve(question)
        if not docs:
            return {"answer": NO_INFO, "docs": []}
        return {"answer": self.generate(question, docs), "docs": docs}


def build_rag_chain(llm=None, embeddings=None, persist_dir: str | None = None, collection_name: str = COLLECTION_NAME, k: int = TOP_K) -> RagChain:
    """`llm` / `embeddings` are injectable (offline tests); by default Gemini models configured through the environment."""
    from langchain_community.vectorstores import Chroma

    if embeddings is None or llm is None:
        from common import llm as llm_factory

        embeddings = embeddings or llm_factory.get_embeddings()
        llm = llm or llm_factory.get_chat_model(temperature=0.1)
    vectorstore = Chroma(persist_directory=persist_dir or CHROMA_DIR, embedding_function=embeddings, collection_name=collection_name)
    if vectorstore._collection.count() == 0:
        raise RuntimeError("The knowledge base is empty. Run `python ai/rag/ingest.py` first.")
    return RagChain(vectorstore.as_retriever(search_kwargs={"k": k}), llm)


@traceable_if_enabled(
    name="finance_rag_query",
    project_name="AI-Readiness-POC-02-P2",
    process_inputs=lambda inputs: {"question": inputs.get("question")},
)
def ask_question(question: str, chain: RagChain) -> dict:
    question = (question or "").strip()
    if not question:
        return {"answer": EMPTY_QUESTION, "sources": [], "source_details": []}
    started = time.perf_counter()
    try:
        result = chain.invoke(question)
    except Exception as exc:  # noqa: BLE001
        logger.error("llm_call_failed", error_type=type(exc).__name__, question=question[:80], operation="rag_query", status="failure")
        return {"answer": LLM_UNAVAILABLE, "sources": [], "source_details": [], "error": type(exc).__name__}

    docs = result["docs"]
    if not docs:
        logger.warning("retrieval_empty", question=question[:80])
    details = [{"section": d.metadata.get("section", "Manual"), "snippet": d.page_content[:200]} for d in docs]
    logger.info(
        "rag_query_completed",
        question=question[:80],
        answer_length=len(result["answer"]),
        source_count=len(docs),
        duration_ms=int((time.perf_counter() - started) * 1000),
        operation="rag_query",
        status="success",
    )
    return {"answer": result["answer"], "sources": [d["snippet"] for d in details], "source_details": details}
