import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from llm.client import groq_llm
from llm.service import _clean_model_text
from prompts.main_prompt import SYSTEM

SHARED_TABLES = tuple(
    dict.fromkeys(
        name.lower()
        for name in re.findall(r"SHARED TABLE \(query as ([A-Za-z_][\w.]*)\)", SYSTEM)
    )
)


def generate_sql(
    question: str,
    dialect: str,
    schema: str,
    client_id: str,
    previous_sql: str | None = None,
    error: str | None = None,
) -> dict:
    user = f"Question: {question}"
    if previous_sql:
        user = (
            f"Previous query (the user may be refining it):\n{previous_sql}\n\n{user}"
        )
    if error:
        user += f"\n\nYour last attempt failed: {error}\nReturn a corrected query."

    system = SYSTEM.format(dialect=dialect, schema=schema, client_id=str(client_id))
    result = groq_llm.invoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    raw = result.content if isinstance(result.content, str) else str(result.content)
    cleaned = _clean_model_text(raw).strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1 :] if first_newline != -1 else ""
    if cleaned.rstrip().endswith("```"):
        cleaned = cleaned.rstrip()[:-3].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"sql": None, "reason": "The model did not return valid JSON"}
    if not isinstance(data, dict):
        return {"sql": None, "reason": "Unexpected model output"}
    return data
