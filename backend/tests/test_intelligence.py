from uuid import uuid4

import pytest

from modules.intelligence import service as intelligence_service
from modules.intelligence.router import ask_intelligence
from modules.intelligence.schemas import IntelligenceRequest
from prompts.main_prompt import SYSTEM


def test_generic_voter_list_prompt_uses_basic_fields_only():
    voter_list = SYSTEM.split("Voter list:\n", 1)[1].split(
        "\n\nVoter count by status:", 1
    )[0]
    expected_projection = (
        "SELECT v.voter_cd, v.voter_id, v.list_no, v.fullname, v.age, v.gender, "
        "v.mobileno, v.ac_no, v.ward_no, v.booth_id, v.status_type"
    )
    actual_projection = " ".join(voter_list.split("FROM", 1)[0].split())

    assert actual_projection == expected_projection
    assert "voter_cd, voter_id, list_no, fullname, age, gender, mobileno, ac_no," in SYSTEM
    assert "exactly these 11 columns" in voter_list
    assert "v.idcard_no" not in voter_list
    assert "v.status_type <> 'D'" in voter_list
    assert '"dw_voters_info".ac_no is documented' in SYSTEM


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