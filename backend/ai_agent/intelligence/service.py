import json
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ai_agent.llm.client import groq_llm, xai_llm
from ai_agent.llm.service import (
    _clean_model_text,
    generate_reply,
    is_not_found,
    _invoke_llm_with_fallback,
)
from modules.analysis.schemas import AskRequest
from modules.analysis.service import AnalysisService
from modules.documents.repository import DocumentRepository
from modules.users.models import User
from ai_agent.rag.service import format_context, retrieve, strip_sources

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

POLITICIAN_REFUSAL = (
    "I couldn't verify that specific politician-related information in your "
    "assigned documents or database. I can still help with general political "
    "knowledge and information available in your sources."
)

# Person-specific facts must come from the user's assigned sources, not from
# the general model's potentially outdated or incomplete knowledge.
_POLITICIAN_TERM = re.compile(
    r"\b(?:mla|mla's|mlas|mp|mp's|mps|minister|ministers|chief minister|"
    r"prime minister|president|mayor|corporator|councilor|councillor|"
    r"party president|politician|politicians|political leader|mlc)\b",
    re.IGNORECASE,
)

_CANNED_REPLIES = (NOT_FOUND_REPLY, NO_DOCUMENTS_REPLY)
_GENERAL_UNAVAILABLE = "I'm unable to answer that right now. Please try again later."

# Personal profile detection (utility only â€” not used for short-circuiting).
# The LLM decides how to respond using the user_profile context passed to it.
_PERSONAL_PROFILE_TERM = re.compile(
    r"\b(?:my ward|what is my ward|which ward|my name|what is my name|who am i|"
    r"my assembly|what is my assembly|my party|what is my party|my constituency|"
    r"what is my constituency|my profile|user profile)\b",
    re.IGNORECASE,
)

# Greeting / small-talk fast path: short, obvious social openers that need no
# data lookup, intent classification, or document search. Handled with zero LLM calls.
_GREETING_TERM = re.compile(
    r"\b(?:hi+|hello+|hey+|namaste|namaskar|good\s+(?:morning|afternoon|evening|night)|"
    r"howdy|greetings|yo|sup|hiya|hello there)\b",
    re.IGNORECASE,
)

_GREETING_MIN_WORDS = 4
_GREETING_MAX_CHARS = 60

# Identity / self-description fast path: questions about who the assistant is.
# These need no data lookup â€” answered with a static response, zero LLM calls.
_IDENTITY_TERM = re.compile(
    r"\b(?:who\s+are\s+you|what\s+are\s+you|what\s+is\s+your\s+name|"
    r"tell\s+me\s+about\s+yourself|your\s+name|are\s+you\s+(?:an?\s+)?(?:bot|ai|assistant)|"
    r"what\s+can\s+you\s+do|help\s+me|what\s+do\s+you\s+do)\b",
    re.IGNORECASE,
)

_IDENTITY_MIN_WORDS = 6
_IDENTITY_MAX_CHARS = 80

# Ward access control: detect ward references in questions.
# Matches patterns like "ward 5", "ward 12", "ward no. 3", "ward no 18", etc.
_WARD_REFERENCE_TERM = re.compile(
    r"\bward\s+(?:no\.?\s*)?(\d+)\b",
    re.IGNORECASE,
)

HISTORY_LIMIT = 20
SHORT_QUESTION_CHARS = 80

Intent = str

# Obvious database questions are classified without calling the LLM so that
# clear data requests (voter reports, ward/booth counts, worker lists, etc.)
# are never misrouted to "general".
#
# NOTE: "ward" and "booth" are deliberately excluded here because they appear
# in document questions too (e.g. "what does the report say about ward 5?").
# Only specific database-entity terms trigger the fast path so document
# questions are not misrouted to SQL generation.
_VOTER_TERM = re.compile(r"\b(?:voters?|electors?|panel)\b", re.IGNORECASE)
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
        conversation_id: UUID | None = None,
    ) -> IntelligenceResponse:
        started = datetime.now(UTC)

        # Resolve an existing conversation or create a new one so the chat
        # is persisted to the database like document conversations.
        conversation = self.repository.get_or_create_conversation(
            conversation_id, question[:60]
        )

        intent, _ = self._classify(question)

        # Build user profile context once and pass it to all LLM paths so the
        # model can reference the user's ward, party, assembly, etc. when
        # relevant. The model decides how to use it; no static rules short-circuit.
        user_profile = self._user_profile_context()

        # Greeting / small-talk fast path: zero LLM calls for simple social openers.
        if self._is_greeting(question):
            greeting_answer = self._greeting_reply()
            user_message, assistant_message = self.repository.save_chat_turn(
                conversation.id, question, greeting_answer
            )
            return IntelligenceResponse(
                intent="general",
                answer=greeting_answer,
                database=None,
                document=None,
                chart=None,
                sources=[],
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                created_at=started,
            )

        # Identity / self-description fast path: zero LLM calls for questions
        # like "who are you?", "what can you do?", "help me", etc.
        if self._is_identity_question(question):
            identity_answer = self._identity_reply()
            user_message, assistant_message = self.repository.save_chat_turn(
                conversation.id, question, identity_answer
            )
            return IntelligenceResponse(
                intent="general",
                answer=identity_answer,
                database=None,
                document=None,
                chart=None,
                sources=[],
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                created_at=started,
            )

        # Ward access control: users can only query their assigned ward.
        # Admin users are exempt from this restriction.
        if not self._check_ward_access(question):
            access_denied = (
                f"You can only access data for your assigned ward "
                f"(Ward {getattr(self.user, 'ward_no', 'N/A')}). "
                f"Questions about other wards are not permitted."
            )
            user_message, assistant_message = self.repository.save_chat_turn(
                conversation.id, question, access_denied
            )
            return IntelligenceResponse(
                intent="general",
                answer=access_denied,
                database=None,
                document=None,
                chart=None,
                sources=[],
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                created_at=started,
            )

        # Single-path routing based on classified intent. Each intent reaches
        # exactly one answer source (hybrid reaches two), so a simple question
        # costs at most 2 LLM calls: 1 for classification + 1 for the answer.
        database_result: DatabaseResult | None = None
        document_result: DocumentResult | None = None
        general_answer: str | None = None
        answer: str = ""
        sources: list[DocumentSource] = []
        suggested_question: str | None = None

        if intent == "database":
            database_result = self._run_database(question)
            # If the query failed entirely (sql is empty), present the
            # restructured question suggestion instead of an error.
            if database_result and not database_result.sql:
                suggested_question = database_result.title
                answer = (
                    f"I couldn't generate a query for that question. "
                    f"Try asking: {database_result.title}"
                )
            elif database_result and database_result.sql and database_result.rows:
                answer = self._synthesize_database_answer(
                    question, database_result, user_profile=user_profile
                )
            elif database_result and database_result.sql and not database_result.rows:
                answer = (
                    "I couldn't find any matching records in your assigned "
                    "database for that question. Please try a different ward, "
                    "booth, or filter, or contact your administrator if you "
                    "expect data to be available."
                )

        elif intent == "document":
            document_result = self._run_document(
                question, conversation.id, user_profile=user_profile
            )
            if document_result and document_result.answer not in _CANNED_REPLIES:
                answer = document_result.answer
                sources = document_result.sources
            else:
                # No document answer: fall through to general knowledge so
                # document-intent questions aren't left unanswered.
                if self._is_politician_related(question):
                    answer = POLITICIAN_REFUSAL
                else:
                    answer = self._run_general(
                        question,
                        self.user,
                        fallback_context=(
                            "No relevant information was found in your uploaded "
                            "documents. Give helpful, neutral general political "
                            "context when possible. Clearly distinguish general "
                            "knowledge from local facts; never guess local names, "
                            "counts, results, or other source-specific details."
                        ),
                        user_profile=user_profile,
                    )
                    if not answer or answer == _GENERAL_UNAVAILABLE:
                        answer = (
                            "I couldn't find the answer in your uploaded "
                            "documents. Try rephrasing your question or "
                            "uploading a relevant document."
                        )

        elif intent == "hybrid":
            document_result = self._run_document(
                question, conversation.id, user_profile=user_profile
            )
            database_result = self._run_database(question)

            parts: list[str] = []
            if document_result and document_result.answer not in _CANNED_REPLIES:
                parts.append(document_result.answer)
                sources = document_result.sources
            if database_result and database_result.sql:
                parts.append(
                    self._synthesize_database_answer(
                        question, database_result, user_profile=user_profile
                    )
                )
            if parts:
                answer = self._synthesize_hybrid(
                    question, parts, user_profile=user_profile
                )
            else:
                # Neither documents nor database could answer. Fall through to
                # general knowledge so strategy/recommendation questions still
                # get a useful answer instead of a dead end.
                if self._is_politician_related(question):
                    answer = POLITICIAN_REFUSAL
                else:
                    answer = self._run_general(
                        question,
                        self.user,
                        fallback_context=(
                            "No relevant information was found in your "
                            "uploaded documents or assigned database. Give "
                            "helpful, neutral general political context and "
                            "strategy recommendations when possible. Clearly "
                            "distinguish general knowledge from local facts; "
                            "never guess local names, counts, or results."
                        ),
                        user_profile=user_profile,
                    )
                    if not answer or answer == _GENERAL_UNAVAILABLE:
                        answer = (
                            "I couldn't find relevant information in your "
                            "documents or assigned database. Try rephrasing "
                            "your question or uploading a relevant document."
                        )

        else:  # intent == "general"
            # Ward/assembly-related terms suggest the question may need local
            # data (documents or database). Pure general-knowledge questions
            # skip the document search and go straight to the general model.
            _ward_terms = re.compile(
                r"\b(?:my ward|ward \d+|ward [a-z]+|current situation|ground reality|"
                r"assessment|my assembly|my constituency|performance review|"
                r"performance assessment|worker performance|karyakarta performance|"
                r"political situation|ward situation|ward status)\b",
                re.IGNORECASE,
            )
            has_ward_terms = bool(_ward_terms.search(question))

            if has_ward_terms:
                # Check documents first: if they have a relevant answer, return it
                # directly without any database or general call.
                document_result = self._run_document(
                    question, conversation.id, user_profile=user_profile
                )
                if document_result and document_result.answer not in _CANNED_REPLIES:
                    answer = document_result.answer
                    sources = document_result.sources
                else:
                    # Optional database safety net for ward-scoped questions.
                    try:
                        database_result = self._run_database(question)
                        if database_result and database_result.sql:
                            answer = self._synthesize_database_answer(
                                question, database_result, user_profile=user_profile
                            )
                    except (HTTPException, AttributeError):
                        # AttributeError: analysis_service not set up in tests.
                        database_result = None

                    if not answer:
                        if self._is_politician_related(question):
                            answer = POLITICIAN_REFUSAL
                        else:
                            answer = self._run_general(
                                question,
                                self.user,
                                fallback_context=(
                                    "No relevant information was found in your "
                                    "assigned sources. Give helpful, neutral "
                                    "general political context when possible. "
                                    "Clearly distinguish general knowledge from "
                                    "local facts; never guess local names, "
                                    "counts, results, or other "
                                    "source-specific details."
                                ),
                                user_profile=user_profile,
                            )
                            if not answer or answer == _GENERAL_UNAVAILABLE:
                                answer = (
                                    "I couldn't find a relevant answer in your "
                                    "assigned sources. Try rephrasing your "
                                    "question or adding the relevant document "
                                    "or data."
                                )
            else:
                # Pure general-knowledge question: skip document search, go
                # straight to the general model. Saves one LLM call.
                if self._is_politician_related(question):
                    answer = POLITICIAN_REFUSAL
                else:
                    answer = self._run_general(
                        question,
                        self.user,
                        fallback_context=(
                            "No relevant information was found in your "
                            "assigned sources. Give helpful, neutral general "
                            "political context when possible. Clearly "
                            "distinguish general knowledge from local facts; "
                            "never guess local names, counts, results, or "
                            "other source-specific details."
                        ),
                        user_profile=user_profile,
                    )
                    if not answer or answer == _GENERAL_UNAVAILABLE:
                        answer = (
                            "I couldn't find a relevant answer in your "
                            "assigned sources. Try rephrasing your question "
                            "or adding the relevant document or data."
                        )

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
            suggested_question=suggested_question,
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
            # Use fallback mechanism for intent classification
            cleaned = _invoke_llm_with_fallback(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                primary_llm=groq_llm,
                fallback_llm=xai_llm,
                primary_name="Groq (classify)",
                fallback_name="XAI (classify)",
            )
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

    def _is_politician_related(self, question: str) -> bool:
        """Return True when a question needs person-specific source-backed facts."""
        return bool(_POLITICIAN_TERM.search(question))

    def _is_personal_profile_question(self, question: str) -> bool:
        """Utility: detects questions about the user's own profile (not used for short-circuiting)."""
        return bool(_PERSONAL_PROFILE_TERM.search(question))

    def _is_strategy_or_detail_request(self, question: str) -> bool:
        """Utility: detects strategy/detail requests (not used for short-circuiting)."""
        strategy_terms = re.compile(
            r"\b(?:strateg|plan|30 ?days|detail|details|outreach|campaign|"
            r"booth|voter|worker|supporter|weak|strong|target|list|coverage|"
            r"color.?code|colour.?code|breakdown)\b",
            re.IGNORECASE,
        )
        return bool(strategy_terms.search(question))

    def _user_profile_context(self) -> str:
        """Build a short, factual profile summary from the authenticated user's record."""
        parts: list[str] = []
        name = getattr(self.user, "name", None)
        if name:
            parts.append(f"name: {name}")
        ward_no = getattr(self.user, "ward_no", None)
        if ward_no is not None:
            parts.append(f"ward: {ward_no}")
        assembly_no = getattr(self.user, "assembly_no", None)
        if assembly_no:
            parts.append(f"assembly: {assembly_no}")
        pc = getattr(self.user, "parliamentary_constituency", None)
        if pc:
            parts.append(f"parliamentary constituency: {pc}")
        party_name = getattr(self.user, "party_name", None)
        if party_name:
            parts.append(f"party: {party_name}")
        role = getattr(self.user, "role", None)
        if role:
            parts.append(f"role: {role}")
        if not parts:
            return ""
        return "\nUser profile: " + "; ".join(parts) + "."

    def _is_greeting(self, question: str) -> bool:
        """Detect short social openers (hi, hello, namaste, good morning, etc.)."""
        stripped = question.strip()
        if len(stripped) > _GREETING_MAX_CHARS:
            return False
        if len(stripped.split()) > _GREETING_MIN_WORDS:
            return False
        return bool(_GREETING_TERM.search(stripped))

    def _greeting_reply(self) -> str:
        """Build a personalized greeting using the user's profile context."""
        name = getattr(self.user, "name", None)
        ward_no = getattr(self.user, "ward_no", None)
        party_name = getattr(self.user, "party_name", None)
        role = getattr(self.user, "role", None)

        parts: list[str] = []
        if name:
            parts.append(f"Hello {name}!")
        else:
            parts.append("Hello!")

        context_bits: list[str] = []
        if party_name:
            context_bits.append(f"{party_name} campaign")
        if ward_no is not None:
            context_bits.append(f"Ward {ward_no}")
        if role:
            context_bits.append(f"your role as a {role}")

        if context_bits:
            parts.append(f"How can I help you with {' '.join(context_bits)} today?")
        else:
            parts.append("How can I help you with your political campaign today?")

        parts.append(
            "Feel free to ask about ward-level strategy, outreach ideas, "
            "volunteer performance tracking, voter data, or anything else "
            "related to your campaign."
        )
        return " ".join(parts)

    def _is_identity_question(self, question: str) -> bool:
        """Detect questions about who the assistant is or what it can do."""
        stripped = question.strip()
        if len(stripped) > _IDENTITY_MAX_CHARS:
            return False
        if len(stripped.split()) > _IDENTITY_MIN_WORDS:
            return False
        return bool(_IDENTITY_TERM.search(stripped))

    def _identity_reply(self) -> str:
        """Static self-description â€” no data lookup, zero LLM calls."""
        name = getattr(self.user, "name", None)
        ward_no = getattr(self.user, "ward_no", None)
        party_name = getattr(self.user, "party_name", None)
        role = getattr(self.user, "role", None)

        parts: list[str] = [
            "Hello! I'm Chanakya AI, your political campaign intelligence assistant."
        ]
        parts.append(
            "I can help you with voter data, booth-level insights, "
            "performance metrics, and strategy ideas for your ward and party."
        )

        context_bits: list[str] = []
        if party_name:
            context_bits.append(f"{party_name} campaign")
        if ward_no is not None:
            context_bits.append(f"Ward {ward_no}")
        if role:
            context_bits.append(f"your role as a {role}")

        if context_bits:
            parts.append(f"How can I assist you with {' '.join(context_bits)} today?")
        else:
            parts.append("How can I assist you with your political campaign today?")

        return " ".join(parts)

    def _check_ward_access(self, question: str) -> bool:
        """Return True if the user is allowed to ask about the ward(s) mentioned
        in the question. Admin users have unrestricted access. Other users can
        only query their assigned ward."""
        # Admin users have unrestricted access
        if getattr(self.user, "role", None) == "admin":
            return True

        user_ward = getattr(self.user, "ward_no", None)

        # Find all ward references in the question
        matches = _WARD_REFERENCE_TERM.findall(question)
        if not matches:
            # No specific ward mentioned â€” allow (will be filtered by scope later)
            return True

        # If user has no ward assigned, they cannot query specific wards
        if user_ward is None:
            return False

        # Check if any mentioned ward differs from user's assigned ward
        for ward_str in matches:
            try:
                mentioned_ward = int(ward_str)
                if mentioned_ward != user_ward:
                    return False
            except ValueError:
                continue

        return True

    # ------------------------------------------------------------------ #
    # Database path
    # ------------------------------------------------------------------ #
    def _run_database(self, question: str) -> DatabaseResult:
        result = self.analysis_service.ask(
            AskRequest(question=question),
            self.user.id,
            user=self.user,
        )

        if not result.get("success", True):
            return DatabaseResult(
                title=result.get("restructured_question", ""),
                database=result.get("database", ""),
                tables=[],
                sql="",
                analysis_query_id=None,
                token="",
                columns=[],
                rows=[],
                row_count=0,
                total_time_ms=None,
                page=0,
                page_size=0,
                has_more=False,
            )

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

    def _synthesize_database_answer(
        self, question: str, result: DatabaseResult, user_profile: str = ""
    ) -> str:
        try:
            rows_summary = self._summarize_rows(result.columns, result.rows)
            user_msg = (
                f"Question: {question}\n"
                f"Database: {result.database}\n"
                f"Tables: {', '.join(result.tables)}\n"
                f"Row count: {result.row_count}\n"
                f"Data summary:\n{rows_summary}\n"
                f"{user_profile}"
            )
            # Use fallback mechanism for database answer synthesis
            return _invoke_llm_with_fallback(
                [
                    {"role": "system", "content": DATABASE_ANSWER_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                primary_llm=groq_llm,
                fallback_llm=xai_llm,
                primary_name="Groq (db synthesis)",
                fallback_name="XAI (db synthesis)",
            )
        except Exception as exc:
            logger.warning("Database answer synthesis failed: %s", exc)
            return f"The database query returned {result.row_count or 0} row(s)."

    def _history(self, conversation_id: UUID) -> list[tuple[str, str]]:
        rows, _ = self.repository.message_repo.get_all_by_conversation(
            conversation_id, limit=HISTORY_LIMIT
        )
        rows.reverse()
        return [(m.role.value, strip_sources(m.content)) for m in rows]

    @staticmethod
    def _build_retrieval_query(question: str, history: list[tuple[str, str]]) -> str:
        query = question.strip()
        if len(query) >= SHORT_QUESTION_CHARS:
            return query
        previous = next((c for role, c in reversed(history) if role == "user"), None)
        return f"{previous[:500]} {query}" if previous else query

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
    def _run_document(
        self,
        question: str,
        conversation_id: UUID,
        user_profile: str = "",
    ) -> DocumentResult | None:
        try:
            visible_ids = self.document_repo.visible_ids(self.user)
        except Exception:
            user_id = getattr(self.user, "id", "unknown")
            logger.exception("Failed to list visible documents for user %s", user_id)
            return DocumentResult(answer=NO_DOCUMENTS_REPLY, sources=[])

        if not visible_ids:
            return DocumentResult(answer=NO_DOCUMENTS_REPLY, sources=[])

        history = self._history(conversation_id)
        query = self._build_retrieval_query(question, history)

        try:
            chunks = retrieve(visible_ids, query)
        except Exception:
            user_id = getattr(self.user, "id", "unknown")
            logger.exception("Document retrieval failed for user %s", user_id)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail="Document search is currently unavailable",
            )

        if not chunks:
            return DocumentResult(answer=NOT_FOUND_REPLY, sources=[])

        try:
            raw = generate_reply(
                history=history,
                user_content=(
                    f"{question}{user_profile}" if user_profile else question
                ),
                context=format_context(chunks),
            ).strip()
        except Exception:
            user_id = getattr(self.user, "id", "unknown")
            logger.exception("Document LLM reply failed for user %s", user_id)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail="The language model is currently unavailable",
            )

        if is_not_found(raw):
            return DocumentResult(answer=NOT_FOUND_REPLY, sources=[])

        answer = raw
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
    # General path â€” questions not answerable from database or documents
    # ------------------------------------------------------------------ #
    def _run_general(
        self,
        question: str,
        user: User,
        fallback_context: str | None = None,
        user_profile: str = "",
    ) -> str:
        user_context = user_profile if user_profile else ""

        try:
            # Use fallback mechanism for general answers
            return _invoke_llm_with_fallback(
                [
                    {"role": "system", "content": GENERAL_ANSWER_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"{question}{user_context}"
                            + (
                                f"\n\nSource availability: {fallback_context}"
                                if fallback_context
                                else ""
                            )
                        ),
                    },
                ],
                primary_llm=groq_llm,
                fallback_llm=xai_llm,
                primary_name="Groq (general)",
                fallback_name="XAI (general)",
            )
        except Exception as exc:
            logger.exception("General answer failed: %s", exc)
            return "I'm unable to answer that right now. Please try again later."

    # ------------------------------------------------------------------ #
    # Hybrid synthesis
    # ------------------------------------------------------------------ #
    def _synthesize_hybrid(
        self, question: str, parts: list[str], user_profile: str = ""
    ) -> str:
        try:
            user_msg = (
                f"Question: {question}\n\n"
                + "\n\n".join(f"Part {i + 1}:\n{p}" for i, p in enumerate(parts))
                + f"{user_profile}"
            )
            # Use fallback mechanism for hybrid synthesis
            return _invoke_llm_with_fallback(
                [
                    {"role": "system", "content": HYBRID_SYNTHESIS_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                primary_llm=groq_llm,
                fallback_llm=xai_llm,
                primary_name="Groq (hybrid)",
                fallback_name="XAI (hybrid)",
            )
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
            # Use fallback mechanism for chart suggestion
            cleaned = _invoke_llm_with_fallback(
                [
                    {"role": "system", "content": CHART_SUGGESTION_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                primary_llm=groq_llm,
                fallback_llm=xai_llm,
                primary_name="Groq (chart)",
                fallback_name="XAI (chart)",
            )
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
