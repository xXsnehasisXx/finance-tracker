"""Gemini chat/embedding factories. Models come from the environment; nothing model-specific is hard-coded.

GEMINI_MODEL      chat model id (POC says Gemini 2.0 Flash, shut down by Google; default gemini-3.5-flash-lite)
EMBEDDING_MODEL   embeddings model id (default models/gemini-embedding-001)
GOOGLE_API_KEY    required for live calls (never logged)
"""
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"

# Ids that do not work with the project's API access. A stale value left in an old .env would otherwise override the
# default and fail with "404 ... not found"; it is replaced by the default and a warning is logged.
RETIRED_MODELS = {
    "GEMINI_MODEL": {"gemini-3.6-flash": DEFAULT_CHAT_MODEL, "gemini-2.0-flash": DEFAULT_CHAT_MODEL},
    "EMBEDDING_MODEL": {"models/text-embedding-004": DEFAULT_EMBEDDING_MODEL, "text-embedding-004": DEFAULT_EMBEDDING_MODEL},
}


class MissingApiKeyError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key:
        raise MissingApiKeyError("GOOGLE_API_KEY is not set. Add it to .env to use live Gemini features.")
    return key


def _model_from_env(var: str, default: str) -> str:
    value = (os.getenv(var) or "").strip() or default
    replacement = RETIRED_MODELS[var].get(value)
    if replacement:
        from common.observability import get_logger

        get_logger("llm").warning("retired_model_id_replaced", variable=var, configured=value, using=replacement)
        return replacement
    return value


def chat_model_name() -> str:
    return _model_from_env("GEMINI_MODEL", DEFAULT_CHAT_MODEL)


def embedding_model_name() -> str:
    return _model_from_env("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def get_chat_model(temperature: float = 0.1):
    from langchain_google_genai import ChatGoogleGenerativeAI

    # max_retries/timeout are bounded: the library default (6 retries with backoff) would hang on a bad model id
    return ChatGoogleGenerativeAI(model=chat_model_name(), google_api_key=_api_key(), temperature=temperature, max_retries=2, timeout=60)


def get_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=embedding_model_name(), google_api_key=_api_key())


def message_text(message) -> str:
    """Gemini 3 responses may be a list of content blocks (text / thinking / signature); return only the visible text."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)
