import re

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from .client import llm

BASE_SYSTEM_PROMPT = (
    "You are Chanakya AI, a helpful, accurate and concise assistant. "
    "Use Markdown for formatting and fenced code blocks for code."
)

RAG_SYSTEM_PROMPT = (
    "{base}\n\n"
    "The user has uploaded documents. Excerpts that may be relevant to the "
    "latest question are listed below between <context> tags.\n"
    "Rules:\n"
    "- Prefer the excerpts when they answer the question, and stay faithful to them.\n"
    "- If the excerpts do not contain the answer, say so plainly, then you may "
    "add general knowledge clearly marked as not coming from the documents.\n"
    "- Never invent quotes, numbers or page references.\n"
    "- Do not mention the <context> tags or the numbering; the app shows sources itself.\n\n"
    "<context>\n{context}\n</context>"
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _system_prompt(context: str | None) -> str:
    if context:
        return RAG_SYSTEM_PROMPT.format(base=BASE_SYSTEM_PROMPT, context=context)
    return BASE_SYSTEM_PROMPT


def generate_reply(
    history: list[tuple[str, str]],
    user_content: str,
    context: str | None = None,
) -> str:
    """history must be in chronological order (oldest first)."""
    messages: list[BaseMessage] = [SystemMessage(content=_system_prompt(context))]
    for role, content in history:
        messages.append(
            HumanMessage(content=content) if role == "user"
            else AIMessage(content=content)
        )
    messages.append(HumanMessage(content=user_content))

    result = llm.invoke(messages)
    text = result.content if isinstance(result.content, str) else str(result.content)

    return _THINK_RE.sub("", text).strip()
