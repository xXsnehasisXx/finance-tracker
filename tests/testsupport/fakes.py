"""Deterministic fakes for the mock test tier (no network, no API key)."""
import hashlib
import math
from typing import Any, List

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class HashEmbeddings(Embeddings):
    """Bag-of-words hashing embeddings: overlapping words => higher cosine similarity."""

    model = "hash-embeddings-test"

    def _vec(self, text):
        v = [0.0] * 384
        for w in text.lower().replace(".", " ").replace("?", " ").replace(",", " ").replace(":", " ").split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 384] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class ScriptedChatModel(BaseChatModel):
    """Returns scripted AIMessages in order (last one repeats). Records every prompt it receives.

    Items may be str, AIMessage (incl. tool_calls) or an Exception instance (raised).
    """

    script: List[Any] = []
    calls: List[Any] = []
    step: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(list(messages))
        item = self.script[min(self.step, len(self.script) - 1)]
        self.step += 1
        if isinstance(item, Exception):
            raise item
        message = item if isinstance(item, AIMessage) else AIMessage(content=str(item))
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def prompts(self) -> List[str]:
        return ["\n".join(str(getattr(m, "content", m)) for m in call) for call in self.calls]
