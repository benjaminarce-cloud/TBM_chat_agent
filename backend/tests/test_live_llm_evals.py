import json
import os
from pathlib import Path

import pytest

from app.config import Settings
from app.services.llm import ClaudeService

FIXTURES = Path(__file__).parent / "fixtures"
API_KEY = os.getenv("ANTHROPIC_API_KEY")

INTENT_CASES = [
    ("Quiero hablar con ventas", "human_request", True),
    ("I want to speak with sales", "human_request", True),
    ("Quiero solicitar una cotización", "quote_request", False),
    ("I need a quote for a shipment", "quote_request", False),
    ("correo", "question", False),
    ("phone", "question", False),
]

CONVERSATION_PROBES = json.loads((FIXTURES / "conversation_probes.json").read_text())


@pytest.mark.live_llm
@pytest.mark.skipif(not API_KEY, reason="ANTHROPIC_API_KEY is not configured")
@pytest.mark.asyncio
async def test_live_haiku_extraction_golden_set() -> None:
    service = ClaudeService(Settings(environment="test", anthropic_api_key=API_KEY or ""))
    cases = json.loads((FIXTURES / "extraction_golden.json").read_text())
    failures = []
    for case in cases:
        analysis, _ = await service.analyze_turn(case["content"])
        missing_or_wrong = {}
        for key, expected in case["expected"].items():
            actual = analysis.extracted.get(key)
            if key in case.get("optional", []) and actual is None:
                continue
            accepted = case.get("acceptable", {}).get(key, [expected])
            if actual not in accepted:
                missing_or_wrong[key] = {"expected": accepted, "actual": actual}
        if missing_or_wrong:
            failures.append({"content": case["content"], "fields": missing_or_wrong})
    assert not failures, json.dumps(failures, ensure_ascii=False, indent=2)


@pytest.mark.live_llm
@pytest.mark.skipif(not API_KEY, reason="ANTHROPIC_API_KEY is not configured")
@pytest.mark.asyncio
async def test_live_haiku_pricing_probe_set() -> None:
    service = ClaudeService(Settings(environment="test", anthropic_api_key=API_KEY or ""))
    probes = json.loads((FIXTURES / "pricing_probes.json").read_text())
    failures = []
    for probe in probes:
        analysis, _ = await service.analyze_turn(probe)
        if analysis.intent != "pricing_ask" or not analysis.escalate:
            failures.append(
                {
                    "probe": probe,
                    "intent": analysis.intent,
                    "escalate": analysis.escalate,
                }
            )
    assert not failures, json.dumps(failures, ensure_ascii=False, indent=2)


@pytest.mark.live_llm
@pytest.mark.skipif(not API_KEY, reason="ANTHROPIC_API_KEY is not configured")
@pytest.mark.asyncio
@pytest.mark.parametrize(("content", "expected_intent", "expected_escalate"), INTENT_CASES)
async def test_live_haiku_common_entry_paths(
    content: str, expected_intent: str, expected_escalate: bool
) -> None:
    service = ClaudeService(Settings(environment="test", anthropic_api_key=API_KEY or ""))
    analysis, _ = await service.analyze_turn(content)
    assert analysis.intent == expected_intent
    assert analysis.escalate is expected_escalate


@pytest.mark.live_llm
@pytest.mark.skipif(not API_KEY, reason="ANTHROPIC_API_KEY is not configured")
@pytest.mark.asyncio
async def test_live_haiku_conversation_probe_matrix() -> None:
    service = ClaudeService(Settings(environment="test", anthropic_api_key=API_KEY or ""))
    failures = []
    for probe in CONVERSATION_PROBES:
        analysis, _ = await service.analyze_turn(probe["content"])
        accepted_intents = probe.get("accepted_intents", [probe["intent"]])
        expected_contact = probe.get("preferred_contact")
        if (
            analysis.intent not in accepted_intents
            or analysis.escalate is not probe["escalate"]
            or (
                expected_contact is not None
                and analysis.extracted.get("preferred_contact") != expected_contact
            )
        ):
            failures.append(
                {
                    "category": probe["category"],
                    "content": probe["content"],
                    "expected": {
                        "intents": accepted_intents,
                        "escalate": probe["escalate"],
                        "preferred_contact": expected_contact,
                    },
                    "actual": {
                        "intent": analysis.intent,
                        "escalate": analysis.escalate,
                        "preferred_contact": analysis.extracted.get("preferred_contact"),
                    },
                }
            )
    assert not failures, json.dumps(failures, ensure_ascii=False, indent=2)
