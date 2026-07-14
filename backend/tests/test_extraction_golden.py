import json
from pathlib import Path

import pytest

from app.schemas import TurnAnalysis

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
