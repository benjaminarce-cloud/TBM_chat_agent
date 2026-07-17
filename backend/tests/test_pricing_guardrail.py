import json
from pathlib import Path

import pytest

from app.schemas import TurnAnalysis
from app.services.safety import (
    closing_handoff,
    contains_price_value,
    forced_response,
    human_handoff,
    is_closing_reply,
    preserve_contact_context,
)

PROBES = json.loads((Path(__file__).parent / "fixtures" / "pricing_probes.json").read_text())


def test_pricing_probe_set_has_at_least_twenty_cases() -> None:
    assert len(PROBES) >= 20


@pytest.mark.parametrize("probe", PROBES)
@pytest.mark.parametrize("locale", ["en", "es"])
def test_haiku_pricing_result_always_forces_a_number_free_pivot(probe: str, locale: str) -> None:
    analysis = TurnAnalysis(
        intent="pricing_ask",
        escalate=True,
        escalate_reason=f"pricing probe: {probe[:30]}",
        extracted={},
    )
    response = forced_response(analysis, locale)
    assert response is not None
    assert not contains_price_value(response)


@pytest.mark.parametrize(
    "unsafe",
    [
        "It is $500.",
        "Serían 900 USD.",
        "The rate is 2.50 per mile.",
        "Cuesta MXN 3000.",
        "The cost would be 700.",
        "That would be 500 bucks.",
        "The price is five hundred dollars.",
        "La tarifa sería mil pesos.",
    ],
)
def test_model_authored_price_values_are_detected_before_streaming(unsafe: str) -> None:
    assert contains_price_value(unsafe)


@pytest.mark.parametrize(
    ("content", "method"),
    [
        ("correo", "email"),
        ("corrre", "email"),
        ("email", "email"),
        ("teléfono", "phone"),
        ("WhatsApp", "whatsapp"),
    ],
)
def test_short_contact_reply_is_not_lost_as_off_topic(content: str, method: str) -> None:
    analysis = TurnAnalysis(intent="off_topic", escalate=False, extracted={})
    preserved = preserve_contact_context(analysis, content)
    assert preserved.intent == "question"
    assert preserved.extracted["preferred_contact"] == method
    response = forced_response(preserved, "es")
    assert response is not None
    assert (
        "correo" in response.lower()
        or "teléfono" in response.lower()
        or "whatsapp" in response.lower()
    )


@pytest.mark.parametrize(
    "content",
    [
        "no",
        "No, gracias.",
        "eso es todo",
        "nada más",
        "no thanks",
        "No, thank you.",
        "nothing else",
        "that's all",
    ],
)
def test_short_closing_replies_are_recognized(content: str) -> None:
    assert is_closing_reply(content)


@pytest.mark.parametrize(
    "content",
    ["no tengo correo", "no sé la fecha", "nothing else is ready", "all set for Monday"],
)
def test_qualification_answers_are_not_mistaken_for_closing_replies(content: str) -> None:
    assert not is_closing_reply(content)


def test_closing_handoff_confirms_sales_follow_up_in_both_languages() -> None:
    assert "sales team" in closing_handoff("en")
    assert "equipo de ventas" in closing_handoff("es")


@pytest.mark.parametrize(
    ("locale", "sales_label", "contact_options"),
    [
        ("en", "sales specialist", ("email", "phone")),
        ("es", "especialista de ventas", ("correo electrónico", "teléfono")),
    ],
)
def test_human_handoff_uses_conversational_sales_intake_copy(
    locale: str, sales_label: str, contact_options: tuple[str, str]
) -> None:
    response = human_handoff(locale).lower()
    assert sales_label in response
    assert all(option in response for option in contact_options)
    assert response.endswith("?")

    forced = forced_response(
        TurnAnalysis(intent="human_request", escalate=True, extracted={}), locale
    )
    assert forced == human_handoff(locale)
