from uuid import uuid4

import pytest

from ai_agent.intelligence import service as intelligence_service
from ai_agent.intelligence.router import ask_intelligence
from ai_agent.intelligence.schemas import DocumentResult, IntelligenceRequest
from ai_agent.prompts.main_prompt import SYSTEM


def test_generic_voter_list_prompt_uses_basic_fields_only():
    assert "voter_cd" in SYSTEM
    assert "fullname" in SYSTEM
    assert "ward_no" in SYSTEM
    assert "booth_id" in SYSTEM
    assert "status_type" in SYSTEM
    assert "status_type <> 'D'" in SYSTEM
    assert '"dw_voters_info".ac_no is documented' in SYSTEM
    assert "COUNT(DISTINCT voter_cd)" in SYSTEM


@pytest.mark.parametrize(
    "question",
    [
        "give me a list of voters",
        "show voter details for booth 12",
        "how many voters are in ward 5?",
        "list of electors",
    ],
)
def test_voter_record_requests_are_routed_to_database(question, monkeypatch):
    def unexpected_llm_call(*args, **kwargs):
        pytest.fail("explicit voter data requests should not need intent classification")

    monkeypatch.setattr(
        type(intelligence_service.groq_llm), "invoke", unexpected_llm_call
    )
    service = object.__new__(intelligence_service.IntelligenceService)

    assert service._classify(question) == ("database", {})


def test_intelligence_router_uses_body_conversation_id():
    conversation_id = uuid4()

    class ServiceStub:
        def ask(self, question, client_id, conversation_id):
            return question, client_id, conversation_id

    result = ask_intelligence(
        IntelligenceRequest(question="hello", conversation_id=conversation_id),
        None,
        None,
        ServiceStub(),
    )

    assert result == ("hello", None, conversation_id)


class _FakeMessage:
    def __init__(self):
        self.id = uuid4()


class _FakeConversation:
    def __init__(self):
        self.id = uuid4()


class _FakeRepository:
    """Minimal stand-in for IntelligenceRepository used to isolate ask()."""

    def __init__(self):
        self.saved_turns = []

    def get_or_create_conversation(self, conversation_id, title):
        return _FakeConversation()

    def save_chat_turn(self, conversation_id, user_content, assistant_content, analysis_query_id=None):
        self.saved_turns.append((user_content, assistant_content))
        return _FakeMessage(), _FakeMessage()


def test_politician_terms_are_detected():
    service = object.__new__(intelligence_service.IntelligenceService)

    assert service._is_politician_related("Who is the MLA of ward 5?")
    assert service._is_politician_related("Tell me about the chief minister")
    assert service._is_politician_related("Information about MP Sharma")
    assert service._is_politician_related("Performance of Corporator X")
    assert service._is_politician_related("Complaints against MLA Y")
    assert service._is_politician_related("Who is the party president?")
    assert service._is_politician_related("Details about the mayor")
    assert service._is_politician_related("Profile of the prime minister")
    assert service._is_politician_related("Is the politician active?")


def test_non_politician_questions_are_not_detected():
    service = object.__new__(intelligence_service.IntelligenceService)

    assert not service._is_politician_related("Give me a list of voters")
    assert not service._is_politician_related("How many voters are in ward 5?")
    assert not service._is_politician_related("Show booth 12 details")
    assert not service._is_politician_related("Which workers are inactive?")
    assert not service._is_politician_related("List of contacts in ward 3")
    assert not service._is_politician_related("hi")


def test_document_backed_politician_question_uses_source_facts(monkeypatch):
    service = object.__new__(intelligence_service.IntelligenceService)
    repo = _FakeRepository()
    service.repository = repo
    service.user = _FakeUser(name="Test User", ward_no=5, role="corporator")

    service._classify = lambda question: ("document", {})
    service._run_document = lambda question, conversation_id, user_profile="": DocumentResult(
        answer="The document lists the elected representative for Ward 5.",
        sources=[],
    )

    def unexpected_general_answer(*args, **kwargs):
        pytest.fail("document-backed facts should not use the general model")

    service._run_general = unexpected_general_answer

    response = service.ask("Who is the MLA of ward 5?")

    assert response.intent == "document"
    assert response.answer == "The document lists the elected representative for Ward 5."
    assert response.database is None
    assert response.document is not None
    assert response.sources == []
    assert repo.saved_turns == [("Who is the MLA of ward 5?", response.answer)]


def test_missing_document_answer_uses_general_knowledge(monkeypatch):
    service = object.__new__(intelligence_service.IntelligenceService)
    repo = _FakeRepository()
    service.repository = repo
    service.user = _FakeUser(name="Test User", ward_no=5, role="corporator")
    fallback_contexts = []
    profile_contexts = []

    service._classify = lambda question: ("document", {})
    service._run_document = lambda question, conversation_id, user_profile="": DocumentResult(
        answer=intelligence_service.NOT_FOUND_REPLY,
        sources=[],
    )

    def general_answer(question, user, fallback_context=None, user_profile=""):
        fallback_contexts.append(fallback_context)
        profile_contexts.append(user_profile)
        return "Here is relevant general political context."

    service._run_general = general_answer

    response = service.ask("What does a ward-level campaign usually involve?")

    assert response.answer == "Here is relevant general political context."
    assert fallback_contexts and "uploaded documents" in fallback_contexts[0]


def test_empty_database_result_does_not_use_general_knowledge(monkeypatch):
    """A pure database question with no rows must not fall back to general
    knowledge, which could invent voter counts or color codes."""
    service = object.__new__(intelligence_service.IntelligenceService)
    service.repository = _FakeRepository()
    service.user = _FakeUser(name="Test User", ward_no=5, role="corporator")
    service._classify = lambda question: ("database", {})
    service._run_database = lambda question, client_id: intelligence_service.DatabaseResult(
        sql="SELECT 1",
        token="query-token",
        rows=[],
        columns=[],
    )
    service._synthesize_database_answer = lambda question, result, user_profile="": "No matching records."
    general_called = []

    def general_answer(question, user, fallback_context=None, user_profile=""):
        general_called.append(True)
        return "Here is relevant general political context."

    service._run_general = general_answer

    response = service.ask("Voter color code analysis report for ward 5")

    assert general_called == [], "general model must not be called for empty DB results"
    assert "couldn't find any matching records" in response.answer
    assert "assigned database" in response.answer


def test_general_route_does_not_append_irrelevant_general_answer(monkeypatch):
    service = object.__new__(intelligence_service.IntelligenceService)
    service.repository = _FakeRepository()
    service.user = _FakeUser(name="Test User", ward_no=5, role="corporator")
    service._classify = lambda question: ("general", {})
    service._run_document = lambda question, conversation_id, user_profile="": DocumentResult(
        answer="The report lists the party composition for Ward 5.",
        sources=[],
    )

    def unexpected_general_answer(*args, **kwargs):
        pytest.fail("a relevant document answer should be returned by itself")

    service._run_general = unexpected_general_answer

    response = service.ask("What party composition is listed for Ward 5?")

    assert response.answer == "The report lists the party composition for Ward 5."


class _FakeUser:
    def __init__(self, **kwargs):
        self.name = kwargs.get("name")
        self.ward_no = kwargs.get("ward_no")
        self.assembly_no = kwargs.get("assembly_no")
        self.parliamentary_constituency = kwargs.get("parliamentary_constituency")
        self.party_name = kwargs.get("party_name")


def test_personal_profile_questions_are_detected():
    service = object.__new__(intelligence_service.IntelligenceService)

    assert service._is_personal_profile_question("What is my ward?")
    assert service._is_personal_profile_question("My ward number?")
    assert service._is_personal_profile_question("What is my name?")
    assert service._is_personal_profile_question("Who am I?")
    assert service._is_personal_profile_question("My assembly?")
    assert service._is_personal_profile_question("What is my party?")
    assert service._is_personal_profile_question("What is my constituency?")


def test_non_profile_questions_are_not_detected():
    service = object.__new__(intelligence_service.IntelligenceService)

    assert not service._is_personal_profile_question("Give me a list of voters")
    assert not service._is_personal_profile_question("How many voters are in ward 5?")
    assert not service._is_personal_profile_question("hi")


def test_profile_context_passed_to_llm(monkeypatch):
    """User profile context is passed to the LLM instead of being short-circuited
    by static rules. The LLM decides how to respond."""
    service = object.__new__(intelligence_service.IntelligenceService)
    repo = _FakeRepository()
    service.repository = repo
    service.user = _FakeUser(
        name="Sahil Tejam",
        ward_no=5,
        party_name="Shiv Sena",
    )
    service._classify = lambda question: ("general", {})
    service._run_document = lambda question, conversation_id, user_profile="": DocumentResult(
        answer=intelligence_service.NOT_FOUND_REPLY,
        sources=[],
    )

    captured = {}

    def general_answer(question, user, fallback_context=None, user_profile=""):
        captured["question"] = question
        captured["user_profile"] = user_profile
        return "Here is a strategy for your ward based on general political knowledge."

    service._run_general = general_answer

    response = service.ask("current situation in my ward and what are the decision i can take for the future growth")

    assert "ward: 5" in captured["user_profile"]
    assert "name: Sahil Tejam" in captured["user_profile"]
    assert "party: Shiv Sena" in captured["user_profile"]
    assert response.answer == "Here is a strategy for your ward based on general political knowledge."
    assert repo.saved_turns == [("current situation in my ward and what are the decision i can take for the future growth", response.answer)]


def test_profile_context_empty_when_no_fields(monkeypatch):
    """When the user has no assigned profile fields, an empty context is passed."""
    service = object.__new__(intelligence_service.IntelligenceService)
    repo = _FakeRepository()
    service.repository = repo
    service.user = _FakeUser()
    service._classify = lambda question: ("general", {})
    service._run_document = lambda question, conversation_id, user_profile="": DocumentResult(
        answer=intelligence_service.NOT_FOUND_REPLY,
        sources=[],
    )

    captured = {}

    def general_answer(question, user, fallback_context=None, user_profile=""):
        captured["user_profile"] = user_profile
        return "General response."

    service._run_general = general_answer

    response = service.ask("What is my ward?")

    assert captured["user_profile"] == ""
    assert response.answer == "General response."


def test_strategy_request_is_not_treated_as_profile(monkeypatch):
    service = object.__new__(intelligence_service.IntelligenceService)

    assert service._is_strategy_or_detail_request("30 days strategies for my ward")
    assert service._is_strategy_or_detail_request("give me a detail and strategy for ward 11")
    assert service._is_strategy_or_detail_request("outreach plan for ward 5")
    assert not service._is_strategy_or_detail_request("What is my ward?")
    assert not service._is_strategy_or_detail_request("My name?")
    assert not service._is_strategy_or_detail_request("hi")


def test_ward_strategy_routes_to_general_not_profile(monkeypatch):
    service = object.__new__(intelligence_service.IntelligenceService)
    repo = _FakeRepository()
    service.repository = repo
    service.user = _FakeUser(name="Ketan Dohale", ward_no=5, party_name="Shiv Sena")
    general_answers = []

    service._classify = lambda question: ("general", {})
    service._run_document = lambda question, conversation_id, user_profile="": DocumentResult(
        answer=intelligence_service.NOT_FOUND_REPLY,
        sources=[],
    )

    def general_answer(question, user, fallback_context=None, user_profile=""):
        general_answers.append((question, user_profile))
        return "Here is a 30-day ward strategy outline..."

    service._run_general = general_answer

    response = service.ask("30 days strategies for my ward")

    assert response.answer == "Here is a 30-day ward strategy outline..."
    assert general_answers[0][0] == "30 days strategies for my ward"
    assert "ward: 5" in general_answers[0][1]
    assert "name: Ketan Dohale" in general_answers[0][1]
    assert repo.saved_turns == [("30 days strategies for my ward", response.answer)]


# ---------------------------------------------------------------------------
# Role hierarchy tests
# ---------------------------------------------------------------------------

def test_role_hierarchy_ordering():
    from modules.admin.schemas import ROLE_HIERARCHY

    assert ROLE_HIERARCHY["karyakarta"] < ROLE_HIERARCHY["corporator"]
    assert ROLE_HIERARCHY["corporator"] < ROLE_HIERARCHY["aamdar"]
    assert ROLE_HIERARCHY["aamdar"] < ROLE_HIERARCHY["khasdar"]
    assert ROLE_HIERARCHY["khasdar"] < ROLE_HIERARCHY["admin"]


def test_account_create_requires_ward_for_karyakarta():
    from modules.admin.schemas import AccountCreate

    with pytest.raises(ValueError, match="ward_no is required"):
        AccountCreate(
            name="Test Worker",
            email="worker@example.com",
            password="password123",
            role="karyakarta",
        )


def test_account_create_requires_ward_for_corporator():
    from modules.admin.schemas import AccountCreate

    with pytest.raises(ValueError, match="ward_no is required"):
        AccountCreate(
            name="Test Corporator",
            email="corp@example.com",
            password="password123",
            role="corporator",
        )


def test_account_create_requires_assembly_for_aamdar():
    from modules.admin.schemas import AccountCreate

    with pytest.raises(ValueError, match="assembly_no is required"):
        AccountCreate(
            name="Test Aamdar",
            email="aamdar@example.com",
            password="password123",
            role="aamdar",
        )


def test_account_create_requires_pc_for_khasdar():
    from modules.admin.schemas import AccountCreate

    with pytest.raises(ValueError, match="parliamentary_constituency is required"):
        AccountCreate(
            name="Test Khasdar",
            email="khasdar@example.com",
            password="password123",
            role="khasdar",
        )


def test_account_create_valid_with_scope():
    from modules.admin.schemas import AccountCreate

    user = AccountCreate(
        name="Test Karyakarta",
        email="karyakarta@example.com",
        password="password123",
        role="karyakarta",
        ward_no=5,
    )
    assert user.role == "karyakarta"
    assert user.ward_no == 5

    user2 = AccountCreate(
        name="Test Khasdar",
        email="khasdar@example.com",
        password="password123",
        role="khasdar",
        parliamentary_constituency="PC 10",
    )
    assert user2.role == "khasdar"
    assert user2.parliamentary_constituency == "PC 10"


def test_account_create_invalid_role():
    from modules.admin.schemas import AccountCreate

    with pytest.raises(ValueError, match="Invalid role"):
        AccountCreate(
            name="Test",
            email="test@example.com",
            password="password123",
            role="super_user",
        )


def test_user_scope_karyakarta():
    from api.dependencies import user_scope
    from modules.users.models import User

    user = User(
        id=uuid4(),
        name="Worker",
        email="worker@example.com",
        hashed_password="unused",
        role="karyakarta",
        ward_no="Ward 3",
    )
    scope = user_scope(user)
    assert scope["ward_no"] == "Ward 3"
    assert scope["assembly_no"] is None
    assert scope["parliamentary_constituency"] is None


def test_user_scope_corporator():
    from api.dependencies import user_scope
    from modules.users.models import User

    user = User(
        id=uuid4(),
        name="Corporator",
        email="corp@example.com",
        hashed_password="unused",
        role="corporator",
        ward_no="Ward 7",
    )
    scope = user_scope(user)
    assert scope["ward_no"] == "Ward 7"


def test_user_scope_aamdar():
    from api.dependencies import user_scope
    from modules.users.models import User

    user = User(
        id=uuid4(),
        name="Aamdar",
        email="aamdar@example.com",
        hashed_password="unused",
        role="aamdar",
        assembly_no="Assembly 12",
    )
    scope = user_scope(user)
    assert scope["assembly_no"] == "Assembly 12"


def test_user_scope_khasdar():
    from api.dependencies import user_scope
    from modules.users.models import User

    user = User(
        id=uuid4(),
        name="Khasdar",
        email="khasdar@example.com",
        hashed_password="unused",
        role="khasdar",
        parliamentary_constituency="PC 5",
    )
    scope = user_scope(user)
    assert scope["parliamentary_constituency"] == "PC 5"


def test_user_scope_admin_no_filter():
    from api.dependencies import user_scope
    from modules.users.models import User

    user = User(
        id=uuid4(),
        name="Admin",
        email="admin@example.com",
        hashed_password="unused",
        role="admin",
    )
    scope = user_scope(user)
    assert scope["ward_no"] is None
    assert scope["assembly_no"] is None
    assert scope["parliamentary_constituency"] is None


def test_scope_filter_clause_builds_ward_filter():
    from modules.analysis.service import _scope_filter_clause

    clause = _scope_filter_clause({"ward_no": "Ward 5"}, "postgres")
    assert clause is not None
    assert "ward_no = 'Ward 5'" in clause


def test_scope_filter_clause_builds_assembly_filter():
    from modules.analysis.service import _scope_filter_clause

    clause = _scope_filter_clause({"assembly_no": "Assembly 12"}, "postgres")
    assert clause is not None
    # assembly scope uses booth_ac_no and ac_no (columns that actually exist)
    assert "booth_ac_no = 'Assembly 12'" in clause or "ac_no = 'Assembly 12'" in clause


def test_scope_filter_clause_none_for_empty_scope():
    from modules.analysis.service import _scope_filter_clause

    assert _scope_filter_clause({}, "postgres") is None