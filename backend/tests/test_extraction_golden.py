import json
from pathlib import Path

import pytest

from app.schemas import TurnAnalysis
from app.services.llm import stabilize_analysis

FIXTURES = Path(__file__).parent / "fixtures"


def test_extraction_golden_set_has_at_least_thirty_cases() -> None:
    cases = json.loads((FIXTURES / "extraction_golden.json").read_text())
    assert len(cases) >= 30


@pytest.mark.parametrize("case", json.loads((FIXTURES / "extraction_golden.json").read_text()))
def test_golden_expected_fields_match_strict_haiku_schema(case: dict) -> None:
    output = {
        "intent": case["intent"],
        "escalate": False,
        "escalate_reason": None,
        "extracted": case["expected"],
    }
    parsed = TurnAnalysis.model_validate(output)
    assert parsed.extracted == case["expected"]


@pytest.mark.parametrize(
    ("content", "model_phone", "language", "expected"),
    [
        ("Mi teléfono es 664 123 4567.", "+1664123456", None, "+526641234567"),
        ("Call me at (915) 555-0188.", "(915) 555-0188", "en", "+19155550188"),
        (
            "text me +1-520-555-0199",
            "+1-520-555-0199",
            "en",
            "+15205550199",
        ),
    ],
)
def test_direct_phone_values_are_stabilized_before_persistence(
    content: str, model_phone: str, language: str | None, expected: str
) -> None:
    extracted = {"phone": model_phone}
    if language:
        extracted["language"] = language
    analysis = TurnAnalysis(intent="question", escalate=False, extracted=extracted)
    assert stabilize_analysis(content, analysis).extracted["phone"] == expected


@pytest.mark.parametrize(
    ("content", "model_preference", "expected"),
    [
        ("text me +1-520-555-0199", "whatsapp", "phone"),
        ("WhatsApp +52 81 1234 5678", "phone", "whatsapp"),
        ("Email works best: shipping@example.com", "phone", "email"),
    ],
)
def test_explicit_contact_cues_override_model_formatting_drift(
    content: str, model_preference: str, expected: str
) -> None:
    analysis = TurnAnalysis(
        intent="question",
        escalate=False,
        extracted={"preferred_contact": model_preference},
    )
    assert stabilize_analysis(content, analysis).extracted["preferred_contact"] == expected
