import re

from app.schemas import LeadExtraction, TurnAnalysis

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


SHORT_CLOSING_REPLY_PATTERN = re.compile(
    r"^(?:"
    r"no(?:pe)?(?:\s*[,;:]?\s*(?:gracias|thanks|thank\s+you))?|"
    r"(?:eso|esto|ya)\s+es\s+todo|"
    r"nada\s+m[aá]s|"
    r"(?:con\s+eso\s+)?(?:estoy|estamos)\s+bien|"
    r"that(?:'s|\s+is)\s+all|"
    r"nothing\s+else|"
    r"(?:i(?:'m|\s+am)\s+)?all\s+set"
    r")[.!?]*$",
    re.IGNORECASE,
)


def is_closing_reply(content: str) -> bool:
    """Recognize a short decline after qualification without matching longer answers."""
    normalized = " ".join(content.strip().split())
    return bool(SHORT_CLOSING_REPLY_PATTERN.fullmatch(normalized))


def closing_handoff(locale: str) -> str:
    if locale == "en":
        return (
            "It was a pleasure helping you. A member of the TBM sales team will contact you "
            "shortly to continue with your request."
        )
    return (
        "Fue un placer ayudarte. Un miembro del equipo de ventas de TBM te contactará en breve "
        "para continuar con tu solicitud."
    )


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


CONTACT_METHOD_PATTERNS = {
    "email": re.compile(
        r"^(?:(?:correo|corre|corrre)(?:\s+electr[oó]nico)?|e-mail|email|mail)$", re.I
    ),
    "phone": re.compile(r"^(?:tel[eé]fono|tel|phone|llamada|por\s+tel[eé]fono)$", re.I),
    "whatsapp": re.compile(r"^(?:whatsapp|wsp|por\s+whatsapp)$", re.I),
}


def contact_method_hint(content: str) -> str | None:
    """Recognize short contact-channel replies before the LLM classifier can misroute them."""
    normalized = " ".join(content.strip().split())
    for method, pattern in CONTACT_METHOD_PATTERNS.items():
        if pattern.fullmatch(normalized):
            return method
    return None


def preserve_contact_context(analysis: TurnAnalysis, content: str) -> TurnAnalysis:
    """Keep a short contact-channel reply in the qualification flow."""
    method = contact_method_hint(content)
    if method is None:
        return analysis
    extracted = dict(analysis.extracted)
    extracted.setdefault("preferred_contact", method)
    if analysis.intent == "off_topic":
        return TurnAnalysis(
            intent="question",
            escalate=False,
            escalate_reason=None,
            extracted=LeadExtraction.model_validate(extracted).model_dump(
                exclude_none=True, mode="json"
            ),
        )
    return analysis.model_copy(update={"extracted": extracted})


def contact_method_prompt(locale: str, method: str) -> str:
    if locale == "en":
        labels = {"email": "email address", "phone": "phone number", "whatsapp": "WhatsApp number"}
        return f"Perfect — we’ll use {labels.get(method, 'your preferred contact')}. What {labels.get(method, 'contact detail')} should the TBM specialist use?"
    labels = {"email": "correo electrónico", "phone": "teléfono", "whatsapp": "WhatsApp"}
    return f"Perfecto, te contactaremos por {labels.get(method, 'tu medio preferido')}. ¿Cuál es tu {labels.get(method, 'dato de contacto')}?"


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
    preferred_contact = analysis.extracted.get("preferred_contact")
    if (
        not analysis.escalate
        and preferred_contact
        and not analysis.extracted.get("email")
        and not analysis.extracted.get("phone")
    ):
        return contact_method_prompt(locale, preferred_contact)
    if analysis.escalate or analysis.intent == "human_request":
        return human_handoff(locale)
    return None


def should_cap_after_increment(current_count: int, cap: int) -> bool:
    return current_count + 1 >= cap
