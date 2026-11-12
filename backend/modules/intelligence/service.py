import json
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from llm.client import groq_llm
from llm.service import _clean_model_text, generate_reply, is_not_found
from modules.analysis.schemas import AskRequest
from modules.analysis.service import AnalysisService
from modules.documents.repository import DocumentRepository
from modules.users.models import User
from rag.service import format_context, format_sources, retrieve

from .prompts import (
    CHART_SUGGESTION_SYSTEM,
    DATABASE_ANSWER_SYSTEM,
    GENERAL_ANSWER_SYSTEM,
    HYBRID_SYNTHESIS_SYSTEM,
    INTENT_CLASSIFICATION_SYSTEM,
)
from .repository import IntelligenceRepository
from .schemas import (
    ChartAxis,
    ChartConfig,
    DatabaseResult,
    DocumentResult,
    DocumentSource,
    IntelligenceResponse,
)

logger = logging.getLogger(__name__)

NOT_FOUND_REPLY = "I couldn't find the answer in the documents available to you."
NO_DOCUMENTS_REPLY = "No documents are available for your assigned assemblies. Contact your administrator."

Intent = str

# Obvious database questions are classified without calling the LLM so that
# clear data requests (voter reports, ward/booth counts, worker lists, etc.)
# are never misrouted to "general".
_VOTER_TERM = re.compile(r"\b(?:voters?|electors?|panel|ward|booth)\b", re.IGNORECASE)
_DATA_REQUEST_TERM = re.compile(
    r"\b(?:report|list|show|display|count|number|details?|records?|data|summary|breakdown|how many)\b",
    re.IGNORECASE,
)


class IntelligenceService:
    """Hybrid orchestration: classifies a question and routes it to the
    database (SQL analysis), documents (RAG), both, or indicates the question
    cannot be answered from available sources."""

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.analysis_service = AnalysisService(db)
        self.document_repo = DocumentRepository(db)
        self.repository = IntelligenceRepository(db, user)

    def ask(
        self,
        question: str,
        client_id: UUID | None = None,
        conversation_id: UUID | None = None,
    ) -> IntelligenceResponse:
        started = datetime.now(UTC)

        # Resolve an existing conversation or create a new one so the chat
        # is persisted to the database like document conversations.
        conversation = self.repository.get_or_create_conversation(
            conversation_id, question[:60]
        )

        intent, entities = self._classify(question)

        database_result: DatabaseResult | None = None
        document_result: DocumentResult | None = None
        answer_parts: list[str] = []
        sources: list[DocumentSource] = []

        if intent in ("database", "hybrid"):
            database_result = self._run_database(question, client_id)
            if database_result and database_result.sql:
                answer_parts.append(
                    self._synthesize_database_answer(question, database_result)
                )

        if intent in ("document", "hybrid"):
            document_result = self._run_document(question)
            if document_result and document_result.answer:
                answer_parts.append(document_result.answer)
                sources.extend(document_result.sources)

        if intent == "general":
            answer_parts.append(self._run_general(question))

        if intent == "hybrid":
            answer = self._synthesize_hybrid(question, answer_parts)
        elif answer_parts:
            answer = "\n\n".join(answer_parts)
        else:
            answer = "I could not find an answer from your data or documents. Try rephrasing the question."

        chart = self._suggest_chart(question, database_result)

        # Persist the chat (user + assistant messages) to the database.
        user_message, assistant_message = self.repository.save_chat_turn(
            conversation.id,
            question,
            answer,
            analysis_query_id=(
                database_result.analysis_query_id if database_result else None
            ),
        )

        return IntelligenceResponse(
            intent=intent,  # type: ignore[arg-type]
            answer=answer,
            database=database_result,
            document=document_result,
            chart=chart,
            sources=sources,
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            created_at=started,
        )

    # ------------------------------------------------------------------ #
    # Intent classification
    # ------------------------------------------------------------------ #
    def _classify(self, question: str) -> tuple[Intent, dict]:
        # Fast path: obvious database questions never need the LLM classifier.
        if _VOTER_TERM.search(question) and _DATA_REQUEST_TERM.search(question):
            return "database", {}

        system = INTENT_CLASSIFICATION_SYSTEM
        user_msg = f"Question: {question}"

        try:
            result = groq_llm.invoke(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ]
            )
            raw = (
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )
            cleaned = _clean_model_text(raw).strip()
            if cleaned.startswith("```"):
                first_nl = cleaned.find("\n")
                cleaned = cleaned[first_nl + 1 :] if first_nl != -1 else ""
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].strip()
            data = json.loads(cleaned)
        except Exception as exc:
            logger.warning("Intent classification failed: %s", exc)
            return "general", {}

        intent = str(data.get("intent", "general")).strip().lower()
        if intent not in ("database", "document", "hybrid", "general"):
            intent = "general"
        entities = (
            data.get("entities", {}) if isinstance(data.get("entities"), dict) else {}
        )
        return intent, entities

    # ------------------------------------------------------------------ #
    # Database path
    # ------------------------------------------------------------------ #
    def _run_database(self, question: str, client_id: UUID | None) -> DatabaseResult:
        try:
            result = self.analysis_service.ask(
                AskRequest(question=question, client_id=client_id),
                self.user.id,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Database query failed for user %s", self.user.id)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail="The database query is currently unavailable",
            ) from exc

        page = result["result"]
        rows = page.get("rows", [])
        return DatabaseResult(
            title=result["title"],
            database=result["database"],
            tables=result["tables"],
            sql=result["sql"],
            analysis_query_id=result["analysis_query_id"],
            token=result["token"],
            columns=page.get("columns", []),
            rows=rows,
            row_count=len(rows),
            total_time_ms=page.get("total_time_ms"),
            page=page["page"],
            page_size=page["page_size"],
            has_more=page["has_more"],
        )

    def _synthesize_database_answer(self, question: str, result: DatabaseResult) -> str:
        try:
            rows_summary = self._summarize_rows(result.columns, result.rows)
            user_msg = (
                f"Question: {question}\n"
                f"Database: {result.database}\n"
                f"Tables: {', '.join(result.tables)}\n"
                f"Row count: {result.row_count}\n"
                f"Data summary:\n{rows_summary}\n"
            )
            completion = groq_llm.invoke(
                [
                    {"role": "system", "content": DATABASE_ANSWER_SYSTEM},
                    {"role": "user", "content": user_msg},
                ]
            )
            text = (
                completion.content
                if isinstance(completion.content, str)
                else str(completion.content)
            )
            return _clean_model_text(text).strip()
        except Exception as exc:
            logger.warning("Database answer synthesis failed: %s", exc)
            return f"The database query returned {result.row_count or 0} row(s)."

    @staticmethod
    def _summarize_rows(
        columns: list[str], rows: list[list], max_rows: int = 10
    ) -> str:
        if not rows:
            return "(no rows)"
        lines = []
        for row in rows[:max_rows]:
            parts = [f"{col}={val}" for col, val in zip(columns, row)]
            lines.append("; ".join(parts))
        if len(rows) > max_rows:
            lines.append(f"... and {len(rows) - max_rows} more row(s)")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Document path
    # ------------------------------------------------------------------ #
    def _run_document(self, question: str) -> DocumentResult | None:
        try:
            visible_ids = self.document_repo.visible_ids(self.user)
        except Exception:
            logger.exception(
                "Failed to list visible documents for user %s", self.user.id
            )
            return DocumentResult(answer=NO_DOCUMENTS_REPLY, sources=[])

        if not visible_ids:
            return DocumentResult(answer=NO_DOCUMENTS_REPLY, sources=[])

        try:
            chunks = retrieve(visible_ids, question)
        except Exception:
            logger.exception("Document retrieval failed for user %s", self.user.id)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail="Document search is currently unavailable",
            )

        if not chunks:
            return DocumentResult(answer=NOT_FOUND_REPLY, sources=[])

        history: list[tuple[str, str]] = []
        try:
            raw = generate_reply(
                history=history,
                user_content=question,
                context=format_context(chunks),
            ).strip()
        except Exception:
            logger.exception("Document LLM reply failed for user %s", self.user.id)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail="The language model is currently unavailable",
            )

        if is_not_found(raw):
            return DocumentResult(answer=NOT_FOUND_REPLY, sources=[])

        answer = raw + format_sources(chunks)
        sources = [
            DocumentSource(
                filename=c.filename,
                page=c.page,
                score=getattr(c, "distance", None),
            )
            for c in chunks
        ]
        return DocumentResult(answer=answer, sources=sources)

    # ------------------------------------------------------------------ #
    # General path — questions not answerable from database or documents
    # ------------------------------------------------------------------ #
    def _run_general(self, question: str) -> str:
        try:
            completion = groq_llm.invoke(
                [
                    {"role": "system", "content": GENERAL_ANSWER_SYSTEM},
                    {"role": "user", "content": question},
                ]
            )
            text = (
                completion.content
                if isinstance(completion.content, str)
                else str(completion.content)
            )
            return _clean_model_text(text).strip()
        except Exception as exc:
            logger.exception("General answer failed: %s", exc)
            return "I'm unable to answer that right now. Please try again later."

    # ------------------------------------------------------------------ #
    # Hybrid synthesis
    # ------------------------------------------------------------------ #
    def _synthesize_hybrid(self, question: str, parts: list[str]) -> str:
        try:
            user_msg = f"Question: {question}\n\n" + "\n\n".join(
                f"Part {i + 1}:\n{p}" for i, p in enumerate(parts)
            )
            completion = groq_llm.invoke(
                [
                    {"role": "system", "content": HYBRID_SYNTHESIS_SYSTEM},
                    {"role": "user", "content": user_msg},
                ]
            )
            text = (
                completion.content
                if isinstance(completion.content, str)
                else str(completion.content)
            )
            return _clean_model_text(text).strip()
        except Exception as exc:
            logger.warning("Hybrid synthesis failed: %s", exc)
            return "\n\n".join(parts)

    # ------------------------------------------------------------------ #
    # Chart suggestion
    # ------------------------------------------------------------------ #
    def _suggest_chart(
        self, question: str, result: DatabaseResult | None
    ) -> ChartConfig | None:
        if not result or not result.columns or not result.rows:
            return None

        # Heuristic: only suggest charts for small-to-medium result sets with numeric data
        if len(result.rows) > 200:
            return ChartConfig(type="table")

        try:
            sample = result.rows[:5]
            user_msg = (
                f"Question: {question}\n"
                f"Columns: {result.columns}\n"
                f"Sample rows (JSON): {json.dumps(sample, default=str)}\n"
                f"Total rows: {len(result.rows)}\n"
            )
            completion = groq_llm.invoke(
                [
                    {"role": "system", "content": CHART_SUGGESTION_SYSTEM},
                    {"role": "user", "content": user_msg},
                ]
            )
            raw = (
                completion.content
                if isinstance(completion.content, str)
                else str(completion.content)
            )
            cleaned = _clean_model_text(raw).strip()
            if cleaned.startswith("```"):
                first_nl = cleaned.find("\n")
                cleaned = cleaned[first_nl + 1 :] if first_nl != -1 else ""
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].strip()
            data = json.loads(cleaned)
            return ChartConfig(**data)
        except Exception as exc:
            logger.warning("Chart suggestion failed: %s", exc)
            # Fallback heuristic
            return self._fallback_chart(result.columns, result.rows)

    @staticmethod
    def _fallback_chart(columns: list[str], rows: list[list]) -> ChartConfig | None:
        if not columns or not rows:
            return None
        # If there are at least 2 columns and the last looks numeric, bar chart
        if len(columns) >= 2:
            return ChartConfig(
                type="bar",
                x_axis=ChartAxis(field=columns[0], label=columns[0]),
                y_axis=ChartAxis(field=columns[1], label=columns[1]),
                label_field=columns[0],
                value_field=columns[1],
                limit=10,
            )
        return ChartConfig(type="table")
