import json
from collections import Counter
from pathlib import Path

from app.schemas import TurnAnalysis
from app.services.safety import forced_response

PROBES = json.loads((Path(__file__).parent / "fixtures" / "conversation_probes.json").read_text())


def test_conversation_probe_matrix_has_broad_balanced_coverage() -> None:
    categories = Counter(probe["category"] for probe in PROBES)
    assert len(PROBES) >= 60
    assert categories["human_request"] >= 8
    assert categories["quote_request"] >= 8
    assert categories["pricing"] >= 8
    assert categories["pricing_injection"] >= 12
    assert categories["qualification"] >= 12
    assert categories["company_question"] >= 6
    assert categories["off_topic"] >= 8


def test_probe_expectations_fit_the_strict_classifier_schema() -> None:
    for probe in PROBES:
        accepted_intents = probe.get("accepted_intents", [probe["intent"]])
        assert probe["intent"] in accepted_intents
        if "accepted_intents" in probe:
            assert set(accepted_intents) <= {"quote_request", "question"}
        extracted = {}
        if preferred_contact := probe.get("preferred_contact"):
            extracted["preferred_contact"] = preferred_contact
        parsed = TurnAnalysis(
            intent=probe["intent"],
            escalate=probe["escalate"],
            escalate_reason=None,
            extracted=extracted,
        )
        assert parsed.intent in accepted_intents


def test_every_forced_probe_response_respects_the_expected_route() -> None:
    for probe in PROBES:
        extracted = {}
        if preferred_contact := probe.get("preferred_contact"):
            extracted["preferred_contact"] = preferred_contact
        analysis = TurnAnalysis(
            intent=probe["intent"],
            escalate=probe["escalate"],
            extracted=extracted,
        )
        response = forced_response(analysis, "es")
        if probe["intent"] in {"pricing_ask", "human_request", "off_topic"}:
            assert response
        elif preferred_contact := probe.get("preferred_contact"):
            assert preferred_contact in {"email", "phone", "whatsapp"}
            assert response
        else:
            assert response is None
