"""ChromaDB persistence verification (offline, deterministic embeddings). Run twice via `phase=write` then `phase=reopen`.

Uses a deterministic hashing embedding so similarity ranking is testable without any network/LLM.
"""
import hashlib
import math
import os
import sys

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
import chromadb  # noqa: E402
from langchain_community.vectorstores import Chroma  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402

DIM = 256


class HashEmbeddings(Embeddings):
    """Bag-of-words hashing embedding: overlapping words -> higher cosine similarity."""

    def _vec(self, text):
        v = [0.0] * DIM
        for w in text.lower().replace(".", " ").replace("?", " ").split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


DOCS = [
    ("budget", "To set a monthly budget choose a category enter the monthly limit and save the budget"),
    ("alerts", "Budget alerts fire at 80 percent as warning_80 and at 100 percent as exceeded"),
    ("accounts", "Account types supported are savings checking and credit"),
    ("categories", "Transaction categories are food transport utilities entertainment health salary other"),
    ("savings", "Savings rate equals income minus expenses divided by income times 100"),
] + [(f"filler{i}", f"Filler paragraph number {i} about unrelated gardening and cooking topics") for i in range(20)]

path, phase = sys.argv[1], sys.argv[2]
emb = HashEmbeddings()
res = []


def ok(name, cond, detail=""):
    res.append((name, "PASS" if cond else "FAIL", detail))


if phase == "write":
    # raw chromadb client
    client = chromadb.PersistentClient(path=path)
    try:
        client.delete_collection("finance_manual")
    except Exception:  # noqa: BLE001
        pass
    # LangChain wrapper used by the project code (langchain_community.vectorstores.Chroma)
    docs = [Document(page_content=t, metadata={"source": "user_manual.md", "section": s}) for s, t in DOCS]
    vs = Chroma.from_documents(docs, emb, persist_directory=path, collection_name="finance_manual")
    col = client.get_collection("finance_manual")
    ok("insert: count == 25", col.count() == 25, f"count={col.count()}")
    top = vs.similarity_search("How do I set a monthly budget limit?", k=4)
    ok("similarity: top-4 returned, budget doc ranks first", len(top) == 4 and top[0].metadata["section"] == "budget",
       top[0].metadata["section"])
    scored = vs.similarity_search_with_score("pasta recipe", k=4)
    ok("scores returned (lower=closer) for off-topic query", len(scored) == 4 and all(isinstance(s, float) for _, s in scored))
    ret = vs.as_retriever(search_kwargs={"k": 4}).invoke("budget alerts at 80 percent")
    ok("retriever k=4", len(ret) == 4 and ret[0].metadata["section"] == "alerts", ret[0].metadata["section"])
    filt = vs.similarity_search("anything", k=10, filter={"section": "accounts"})
    ok("metadata filter", len(filt) == 1 and filt[0].metadata["section"] == "accounts")
    peek = col.peek(limit=1)
    ok("peek returns id+document+embedding (spec ING-04)", len(peek["ids"]) == 1 and peek["documents"][0] and peek["embeddings"] is not None)
    # reset semantics (spec: ingest twice must not duplicate)
    client.delete_collection("finance_manual")
    vs = Chroma.from_documents(docs, emb, persist_directory=path, collection_name="finance_manual")
    ok("reset+re-ingest: no duplicates", client.get_collection("finance_manual").count() == 25)
    try:
        client.get_collection("no_such_collection")
        ok("missing collection raises", False)
    except Exception as e:  # noqa: BLE001
        ok("missing collection raises", True, type(e).__name__)
    ok("empty query handled", isinstance(vs.similarity_search("  ", k=4), list))
else:
    client = chromadb.PersistentClient(path=path)
    col = client.get_collection("finance_manual")
    ok("REOPEN (new process): count == 25", col.count() == 25, f"count={col.count()}")
    vs = Chroma(persist_directory=path, embedding_function=emb, collection_name="finance_manual")
    top = vs.similarity_search("Which account types are supported?", k=4)
    ok("REOPEN: similarity search works, accounts doc first", len(top) == 4 and top[0].metadata["section"] == "accounts",
       top[0].metadata["section"])
    vs.add_documents([Document(page_content="Extra doc about the savings rate formula", metadata={"section": "extra"})])
    ok("REOPEN: add after reopen", client.get_collection("finance_manual").count() == 26)

w = max(len(n) for n, _, _ in res)
for n, s, d in res:
    print(f"{s:5} {n:<{w}} {d}")
sys.exit(1 if any(s == "FAIL" for _, s, _ in res) else 0)
