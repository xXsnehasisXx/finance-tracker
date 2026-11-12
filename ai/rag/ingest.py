"""Phase 2 ingestion: load the user manual -> chunk (512/50) -> embed -> store in ChromaDB (collection reset on every run).

Run:  python ai/rag/ingest.py        (needs GOOGLE_API_KEY for live embeddings)
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from common.observability import configure_logging, get_logger, span  # noqa: E402

PHASE = 2
configure_logging(PHASE)
logger = get_logger("rag.ingest", PHASE)

MANUAL_PATH = os.getenv("MANUAL_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_manual.md"))
CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")))
COLLECTION_NAME = "finance_manual"
CHUNK_SIZE, CHUNK_OVERLAP = 512, 50
_HEADING = re.compile(r"^#### (Section \d+: .+)$", re.M)


def section_for(text: str, start: int) -> str:
    """Name of the manual section that contains character offset `start` (used for source display)."""
    found = "Introduction"
    for m in _HEADING.finditer(text):
        if m.start() <= start:
            found = m.group(1).strip()
        else:
            break
    return found


def load_and_split(manual_path: str = MANUAL_PATH):
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    with span("rag.document_load", **{"rag.source": os.path.basename(manual_path)}) as sp:
        documents = TextLoader(manual_path, encoding="utf-8").load()
        sp.set_attribute("document_count", len(documents))
    with span("rag.chunk", chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP) as sp:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=["\n\n", "\n", ".", " "], add_start_index=True
        )
        chunks = splitter.split_documents(documents)
        full_text = documents[0].page_content
        for c in chunks:
            c.metadata["section"] = section_for(full_text, c.metadata.get("start_index", 0))
            c.metadata["source"] = "user_manual.md"
        sp.set_attribute("chunk_count", len(chunks))
    return chunks


def ingest_manual(embeddings=None, persist_dir: str | None = None, manual_path: str | None = None, collection_name: str = COLLECTION_NAME) -> int:
    """Rebuilds the vector store. `embeddings` is injectable for offline tests; defaults to Gemini embeddings."""
    import chromadb
    from chromadb.config import Settings
    from langchain_community.vectorstores import Chroma

    persist_dir = persist_dir or CHROMA_DIR
    started = time.perf_counter()
    chunks = load_and_split(manual_path or MANUAL_PATH)
    if embeddings is None:
        from common.llm import get_embeddings

        embeddings = get_embeddings()

    with span("rag.embed", **{"rag.embedding_model": getattr(embeddings, "model", type(embeddings).__name__)}) as sp:
        client = chromadb.PersistentClient(path=persist_dir, settings=Settings(anonymized_telemetry=False))
        try:
            client.delete_collection(collection_name)
        except Exception:  # noqa: BLE001  (collection did not exist)
            pass
        Chroma.from_documents(documents=chunks, embedding=embeddings, persist_directory=persist_dir, collection_name=collection_name)
        sp.set_attribute("vectors_stored", len(chunks))

    logger.info(
        "manual_ingested",
        chunk_count=len(chunks),
        collection_name=collection_name,
        embedding_seconds=round(time.perf_counter() - started, 2),
        operation="ingest_manual",
        status="success",
    )
    return len(chunks)


if __name__ == "__main__":
    count = ingest_manual()
    print(f"[ingest] Done. {count} chunks stored in {CHROMA_DIR} (collection '{COLLECTION_NAME}').")
