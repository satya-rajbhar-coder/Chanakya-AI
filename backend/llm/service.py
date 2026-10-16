import re

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from .client import groq_llm

NOT_FOUND_TOKEN = "NOT_FOUND"

RAG_SYSTEM_PROMPT = (
    "You are Chanakya AI, a document question-answering assistant.\n"
    "Use Markdown for formatting and fenced code blocks for code.\n\n"
    "When generating Mermaid diagrams:\n"
    "- Always generate valid Mermaid syntax inside a fenced block with the language `mermaid`.\n"
    "- Put node labels containing special characters inside double quotes, "
    'e.g. D["Weekly Off (Sun / 2nd Sat)"].\n'
    "- Do not put Markdown fences inside the Mermaid source itself.\n\n"
    "You may answer ONLY from the document excerpts between <context> tags.\n\n"
    "Rules:\n"
    "- Use ONLY the excerpts. Never use outside or general knowledge, even if you know the answer.\n"
    "- Do not invent information, quotes, numbers, names, or page references.\n"
    f"- If the excerpts do not contain the answer, reply with exactly {NOT_FOUND_TOKEN} and nothing else.\n"
    "- Greetings, chit-chat, opinions, coding help and any question unrelated to the "
    f"documents also get exactly {NOT_FOUND_TOKEN}.\n"
    "- Follow-up questions may use the conversation history to understand what is meant, "
    "but every fact must still come from the excerpts.\n"
    "- Do not mention the <context> tags or internal chunk numbering.\n\n"
    "<context>\n"
    "{context}\n"
    "</context>"
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _clean_model_text(text: str) -> str:
    """Remove model reasoning tags and surrounding whitespace."""
    return _THINK_RE.sub("", text).strip()


def is_not_found(text: str) -> bool:
    return text.strip().strip("`*\"' \n.").upper().startswith(NOT_FOUND_TOKEN)


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

    result = groq_llm.invoke(messages)
    text = result.content if isinstance(result.content, str) else str(result.content)
    return _clean_model_text(text)
