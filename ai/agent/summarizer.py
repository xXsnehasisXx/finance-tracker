"""Compress long tool outputs (> 2000 chars) so the agent context stays small."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from common.llm import message_text  # noqa: E402
from common.observability import get_logger, span  # noqa: E402

logger = get_logger("agent.summarizer", 3)

MAX_CHARS = 2000
FALLBACK_CHARS = 1500

SUMMARY_PROMPT = (
    "Summarize the following financial data concisely. Keep every number, category name and date that matters; "
    "do not add anything that is not in the text.\n\n{text}\n\nSummary:"
)


def summarize_text(text: str, llm=None) -> str:
    """Returns `text` unchanged when short; otherwise an LLM summary (deterministic truncation if the LLM is unavailable)."""
    if len(text) <= MAX_CHARS:
        return text
    with span("agent.summarize", **{"summarize.input_length": len(text)}) as sp:
        try:
            from langchain_core.prompts import PromptTemplate
            from langchain_core.runnables import RunnableLambda

            if llm is None:
                from common.llm import get_chat_model

                llm = get_chat_model(temperature=0)
            summary = (PromptTemplate.from_template(SUMMARY_PROMPT) | llm | RunnableLambda(message_text)).invoke({"text": text}).strip()
            if not summary:
                raise ValueError("empty summary")
        except Exception as exc:  # noqa: BLE001
            logger.warning("summarize_fallback", reason=type(exc).__name__, input_length=len(text))
            summary = text[:FALLBACK_CHARS].rstrip() + " … [truncated: summary unavailable]"
        sp.set_attribute("summarize.output_length", len(summary))
    logger.info("tool_output_summarized", input_length=len(text), output_length=len(summary))
    return summary


def _summarize_if_long(text: str, llm=None) -> str:
    """Helper used by tools: returns short text unchanged."""
    if len(text) <= MAX_CHARS:
        return text
    return summarize_text(text, llm)
