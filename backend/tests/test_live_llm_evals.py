import json
import os
from pathlib import Path

import pytest

from app.config import Settings
from app.services.llm import ClaudeService

FIXTURES = Path(__file__).parent / "fixtures"
API_KEY = os.getenv("ANTHROPIC_API_KEY")


@pytest.mark.live_llm
@pytest.mark.skipif(not API_KEY, reason="ANTHROPIC_API_KEY is not configured")
@pytest.mark.asyncio
async def test_live_haiku_extraction_golden_set() -> None:
    service = ClaudeService(Settings(environment="test", anthropic_api_key=API_KEY or ""))
    cases = json.loads((FIXTURES / "extraction_golden.json").read_text())
    failures = []
    for case in cases:
        analysis, _ = await service.analyze_turn(case["content"])
        missing_or_wrong = {
            key: {"expected": expected, "actual": analysis.extracted.get(key)}
            for key, expected in case["expected"].items()
            if analysis.extracted.get(key) != expected
        }
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
