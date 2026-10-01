# import json
# import re
# from dataclasses import dataclass

# from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

# from .client import groq_llm

# BASE_SYSTEM_PROMPT = (
#     "You are Chanakya AI, a helpful, accurate and concise assistant. "
#     "Use Markdown for formatting and fenced code blocks for code."
# )


# RAG_SYSTEM_PROMPT = (
#     "{base}\n\n"
#     "The user has uploaded documents. Excerpts that may be relevant to the "
#     "latest question are listed below between <context> tags.\n\n"
#     "Rules:\n"
#     "- Prefer the document excerpts when they answer the question.\n"
#     "- Stay faithful to the document excerpts.\n"
#     "- Do not invent information, quotes, numbers, names, or page references.\n"
#     "- If the document excerpts do not contain the answer, clearly say that "
#     "the answer was not found in the uploaded documents.\n"
#     "- You may provide general knowledge only when explicitly useful, and "
#     "clearly state that it is not from the uploaded documents.\n"
#     "- Do not mention the <context> tags or internal chunk numbering.\n\n"
#     "<context>\n"
#     "{context}\n"
#     "</context>"
# )


# @dataclass(frozen=True)
# class QuestionIntent:
#     """
#     Classification result for the user's question.
#     """

#     intent: str
#     confidence: float


# INTENT_SYSTEM_PROMPT = """
# You are an intent classifier for a RAG application.

# The application has two possible intents:

# 1. DOCUMENT
#    The user wants information from their uploaded documents/PDFs.

# 2. GENERAL
#    The user wants general knowledge, explanation, coding help,
#    conversation, or information that does not depend on their
#    uploaded documents.

# Classify ONLY the latest user question.

# Choose DOCUMENT when the question:
# - explicitly refers to the uploaded document/PDF
# - asks "according to the PDF/document"
# - asks about content that is likely specific to the uploaded documents
# - asks for information that must be extracted from the uploaded files
# - asks for a summary, explanation, list, number, name, table value,
#   or fact from the uploaded material

# Choose GENERAL when the question:
# - is clearly independent of the uploaded documents
# - asks general programming questions
# - asks general technical questions
# - asks general definitions
# - asks casual questions
# - asks about common/general knowledge

# Return ONLY valid JSON:

# {
#   "intent": "DOCUMENT" or "GENERAL",
#   "confidence": 0.0
# }

# Do not return Markdown.
# Do not return explanations.
# """


# _THINK_RE = re.compile(
#     r"<think>.*?</think>",
#     re.DOTALL | re.IGNORECASE,
# )


# def _clean_model_text(text: str) -> str:
#     return _THINK_RE.sub(
#         "",
#         text,
#     ).strip()


# def classify_intent(user_content: str) -> QuestionIntent:
#     messages: list[BaseMessage] = [
#         SystemMessage(content=INTENT_SYSTEM_PROMPT),
#         HumanMessage(content=user_content),
#     ]

#     result = groq_llm.invoke(messages)

#     raw = result.content if isinstance(result.content, str) else str(result.content)

#     raw = _clean_model_text(raw)

#     try:
#         data = json.loads(raw)

#         intent = str(data.get("intent", "GENERAL")).upper()

#         confidence = float(data.get("confidence", 0.5))
#         if intent not in {"DOCUMENT", "GENERAL"}:
#             intent = "GENERAL"

#         confidence = max(0.0, min(1.0, confidence))
#         return QuestionIntent(intent=intent, confidence=confidence)

#     except json.JSONDecodeError, TypeError, ValueError:
#         return QuestionIntent(
#             intent="GENERAL",
#             confidence=0.0,
#         )


# def _system_prompt(context: str | None) -> str:
#     if context:
#         return RAG_SYSTEM_PROMPT.format(
#             base=BASE_SYSTEM_PROMPT,
#             context=context,
#         )

#     return BASE_SYSTEM_PROMPT


# def generate_reply(
#     history: list[tuple[str, str]], user_content: str, context: str | None = None
# ) -> str:
#     messages: list[BaseMessage] = [SystemMessage(content=_system_prompt(context))]
#     for role, content in history:
#         if role == "user":
#             messages.append(HumanMessage(content=content))

#         elif role == "assistant":
#             messages.append(AIMessage(content=content))

#     messages.append(HumanMessage(content=user_content))

#     result = groq_llm.invoke(messages)

#     text = result.content if isinstance(result.content, str) else str(result.content)

#     return _clean_model_text(text)


import json
import re
from dataclasses import dataclass

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from .client import groq_llm

BASE_SYSTEM_PROMPT = (
    "You are Chanakya AI, a helpful, accurate and concise assistant. "
    "Use Markdown for formatting and fenced code blocks for code.\n\n"
    "When generating Mermaid diagrams:\n"
    "- Always generate valid Mermaid syntax.\n"
    "- Use fenced Markdown code blocks with the language `mermaid`.\n"
    "- Put node labels containing special characters inside double quotes.\n"
    '- Example: D["Weekly Off (Sun / 2nd Sat)"].\n'
    "- This is especially important for labels containing parentheses, "
    "slashes, colons, ampersands, percentages, or similar characters.\n"
    "- Do not put Markdown fences inside the Mermaid source itself.\n"
)


RAG_SYSTEM_PROMPT = (
    "{base}\n\n"
    "The user has uploaded documents. Excerpts that may be relevant to the "
    "latest question are listed below between <context> tags.\n\n"
    "Rules:\n"
    "- Prefer the document excerpts when they answer the question.\n"
    "- Stay faithful to the document excerpts.\n"
    "- Do not invent information, quotes, numbers, names, or page references.\n"
    "- If the document excerpts do not contain the answer, clearly say that "
    "the answer was not found in the uploaded documents.\n"
    "- You may provide general knowledge only when explicitly useful, and "
    "clearly state that it is not from the uploaded documents.\n"
    "- Do not mention the <context> tags or internal chunk numbering.\n\n"
    "<context>\n"
    "{context}\n"
    "</context>"
)


@dataclass(frozen=True)
class QuestionIntent:
    """
    Classification result for the user's question.
    """

    intent: str
    confidence: float


INTENT_SYSTEM_PROMPT = """
You are an intent classifier for a RAG application.

The application has two possible intents:

1. DOCUMENT
   The user wants information from their uploaded documents/PDFs.

2. GENERAL
   The user wants general knowledge, explanation, coding help,
   conversation, or information that does not depend on their
   uploaded documents.

Classify ONLY the latest user question.

Choose DOCUMENT when the question:
- explicitly refers to the uploaded document/PDF
- asks "according to the PDF/document"
- asks about content that is likely specific to the uploaded documents
- asks for information that must be extracted from the uploaded files
- asks for a summary, explanation, list, number, name, table value,
  or fact from the uploaded material

Choose GENERAL when the question:
- is clearly independent of the uploaded documents
- asks general programming questions
- asks general technical questions
- asks general definitions
- asks casual questions
- asks about common/general knowledge

Return ONLY valid JSON:

{
  "intent": "DOCUMENT" or "GENERAL",
  "confidence": 0.0
}

Do not return Markdown.
Do not return explanations.
"""


_THINK_RE = re.compile(
    r"<think>.*?</think>",
    re.DOTALL | re.IGNORECASE,
)


def _clean_model_text(text: str) -> str:
    """
    Remove model reasoning tags and surrounding whitespace.
    """

    return _THINK_RE.sub("", text).strip()


def classify_intent(user_content: str) -> QuestionIntent:
    messages: list[BaseMessage] = [
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    result = groq_llm.invoke(messages)

    raw = result.content if isinstance(result.content, str) else str(result.content)

    raw = _clean_model_text(raw)

    try:
        data = json.loads(raw)

        intent = str(data.get("intent", "GENERAL")).upper()

        confidence = float(data.get("confidence", 0.5))

        if intent not in {"DOCUMENT", "GENERAL"}:
            intent = "GENERAL"

        confidence = max(
            0.0,
            min(1.0, confidence),
        )

        return QuestionIntent(
            intent=intent,
            confidence=confidence,
        )

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return QuestionIntent(
            intent="GENERAL",
            confidence=0.0,
        )


def _system_prompt(context: str | None) -> str:
    if context and context.strip():
        return RAG_SYSTEM_PROMPT.format(
            base=BASE_SYSTEM_PROMPT,
            context=context,
        )

    return BASE_SYSTEM_PROMPT


def generate_reply(
    history: list[tuple[str, str]],
    user_content: str,
    context: str | None = None,
) -> str:

    messages: list[BaseMessage] = [SystemMessage(content=_system_prompt(context))]

    for role, content in history:
        if role == "user":
            messages.append(HumanMessage(content=content))

        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_content))

    result = groq_llm.invoke(messages)

    text = result.content if isinstance(result.content, str) else str(result.content)

    return _clean_model_text(text)
