import re

from app.schemas import TurnAnalysis

PRICING_OUTPUT_PATTERN = re.compile(
    r"(?:[$£€] ?\s*\d)|"
    r"(?:\b(?:usd|mxn|dollars?|dólares?|pesos?)\s*\d)|"
    r"(?:\b\d+(?:[.,]\d+)?\s*(?:usd|mxn|dollars?|dólares?|pesos?|bucks?|each|cada\s+uno|/\s*(?:mile|mi|milla)|per\s+(?:mile|load)|por\s+(?:milla|viaje)))|"
    r"(?:\b(?:price|rate|cost|quote|charge|precio|tarifa|costo|cotización|sale)\D{0,24}(?:\d|one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|cien|mil))|"
    r"(?:\b(?:one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|cien|mil)(?:[ -](?:hundred|thousand|cientos|mil))?\s+(?:dollars?|dólares?|pesos?|bucks?))",
    re.IGNORECASE,
)


def contains_price_value(text: str) -> bool:
    """Detect a numeric monetary/rate value before any model text reaches the visitor."""
    return bool(PRICING_OUTPUT_PATTERN.search(text))


def pricing_pivot(locale: str) -> str:
    if locale == "en":
        return (
            "I can help get exact pricing from a TBM specialist, but I can’t provide or estimate "
            "rates here. What are the origin, destination, freight type, volume or frequency, "
            "and target shipping date?"
        )
    return (
        "Puedo ayudarte a obtener un precio exacto con un especialista de TBM, pero no puedo "
        "dar ni estimar tarifas aquí. ¿Cuál es el origen, destino, tipo de carga, volumen o "
        "frecuencia y fecha prevista de envío?"
    )


def human_handoff(locale: str) -> str:
    if locale == "en":
        return "Of course. I’m passing this to the TBM team so a specialist can follow up with you."
    return "Claro. Voy a pasar esto al equipo de TBM para que un especialista pueda contactarte."


def off_topic_redirect(locale: str) -> str:
    if locale == "en":
        return (
            "I’m here to help with freight and transportation questions for TBM Carriers. "
            "What do you need to ship, and between which cities?"
        )
    return (
        "Estoy aquí para ayudarte con preguntas de carga y transporte de TBM Carriers. "
        "¿Qué necesitas enviar y entre qué ciudades?"
    )


def capped_handoff(locale: str) -> str:
    if locale == "en":
        return (
            "We’ve reached this chat’s message limit. I’ll hand the conversation to the TBM team "
            "so a specialist can continue with you."
        )
    return (
        "Llegamos al límite de mensajes de este chat. Pasaré la conversación al equipo de TBM "
        "para que un especialista continúe contigo."
    )


def safe_failure(locale: str) -> str:
    if locale == "en":
        return "I’m having trouble completing that. I’ll pass your request to a TBM specialist."
    return "Tengo problemas para completar eso. Pasaré tu solicitud a un especialista de TBM."


def forced_response(analysis: TurnAnalysis, locale: str) -> str | None:
    if analysis.intent == "pricing_ask":
        return pricing_pivot(locale)
    if analysis.intent == "off_topic":
        return off_topic_redirect(locale)
    if analysis.escalate or analysis.intent == "human_request":
        return human_handoff(locale)
    return None


def should_cap_after_increment(current_count: int, cap: int) -> bool:
    return current_count + 1 >= cap
