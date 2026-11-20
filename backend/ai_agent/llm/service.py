import logging
import re
from typing import Any, Callable, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from .client import groq_llm, xai_llm

logger = logging.getLogger(__name__)

NOT_FOUND_TOKEN = "NOT_FOUND"

RAG_SYSTEM_PROMPT = (
    "You are Chanakya AI, a document question-answering assistant.\n"
    "Use Markdown for formatting.\n\n"
    "You may answer ONLY from the document excerpts between <context> tags.\n\n"
    "Rules:\n"
    "- Use ONLY the excerpts. Never use outside or general knowledge.\n"
    "- Do not invent information, quotes, numbers, names, or page references.\n"
    f"- If the excerpts do not contain the answer, reply with exactly {NOT_FOUND_TOKEN} and nothing else.\n"
    f"- Greetings, chit-chat, coding help, and unrelated questions also get exactly {NOT_FOUND_TOKEN}.\n"
    "- Follow-up questions may use conversation history to resolve references, but every fact "
    "must come from the excerpts.\n"
    "- Base recommendations/advice on the retrieved excerpts only; derive suggestions from "
    "what the documents say, not outside campaign knowledge.\n"
    "- Never reveal retrieval metadata, chunk numbers, ranking, or internal context labels. "
    "Sources and page references are shown separately by the app.\n"
    "- Focus on the current question; use earlier turns only to resolve follow-up references.\n\n"
    "<context>\n"
    "{context}\n"
    "</context>"
)

_THINK_RE = re.compile(r"<?xml.*?xml>", re.DOTALL | re.IGNORECASE)


def _clean_model_text(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


def is_not_found(text: str) -> bool:
    return text.strip().strip("`*\"' \n.").upper().startswith(NOT_FOUND_TOKEN)


def _invoke_with_fallback(
    invoke_fn: Callable[[], Any],
    primary_name: str = "primary",
    fallback_fn: Optional[Callable[[], Any]] = None,
    fallback_name: str = "fallback",
) -> Any:
    try:
        logger.debug(f"Invoking {primary_name}")
        result = invoke_fn()
        logger.debug(f"{primary_name} succeeded")
        return result
    except Exception as e:
        logger.warning(f"{primary_name} failed: {type(e).__name__}: {e}")

        if fallback_fn is not None:
            try:
                logger.info(f"Falling back to {fallback_name}")
                result = fallback_fn()
                logger.info(f"{fallback_name} succeeded")
                return result
            except Exception as fallback_error:
                logger.error(
                    f"{fallback_name} also failed: {type(fallback_error).__name__}: {fallback_error}"
                )
                raise RuntimeError(
                    f"Both {primary_name} and {fallback_name} failed. Primary: {e}, Fallback: {fallback_error}"
                )
        else:
            logger.error(f"No fallback available, {primary_name} failed: {e}")
            raise


def _invoke_llm_with_fallback(
    messages: list[BaseMessage],
    primary_llm,
    fallback_llm: Optional = None,
    primary_name: str = "Groq",
    fallback_name: str = "XAI (Grok)",
) -> str:
    """
    Invoke LLM with fallback mechanism.

    Args:
        messages: List of messages to send to the LLM
        primary_llm: Primary LLM instance
        fallback_llm: Fallback LLM instance (optional)
        primary_name: Name of primary LLM for logging
        fallback_name: Name of fallback LLM for logging

    Returns:
        The response text from either primary or fallback LLM
    """

    def primary_invoke():
        result = primary_llm.invoke(messages)
        text = (
            result.content if isinstance(result.content, str) else str(result.content)
        )
        return _clean_model_text(text)

    def fallback_invoke():
        if fallback_llm is None:
            raise RuntimeError("No fallback LLM configured")
        result = fallback_llm.invoke(messages)
        text = (
            result.content if isinstance(result.content, str) else str(result.content)
        )
        return _clean_model_text(text)

    return _invoke_with_fallback(
        primary_invoke,
        primary_name=primary_name,
        fallback_fn=fallback_invoke if fallback_llm is not None else None,
        fallback_name=fallback_name,
    )


def generate_reply(
    history: list[tuple[str, str]],
    user_content: str,
    context: str,
) -> str:
    messages: list[BaseMessage] = [
        SystemMessage(content=RAG_SYSTEM_PROMPT.replace("{context}", context))
    ]

    for role, content in history:
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_content))

    # Use Groq as primary, XAI as fallback
    return _invoke_llm_with_fallback(
        messages,
        primary_llm=groq_llm,
        fallback_llm=xai_llm,
        primary_name="Groq",
        fallback_name="XAI (Grok)",
    )
