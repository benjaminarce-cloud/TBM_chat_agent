import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from app.config import Settings
from app.schemas import LeadExtraction, TurnAnalysis

SONNET_PROMPT_TEMPLATE = """You are TBM Carriers' bilingual sales assistant, embedded on the TBM Carriers website.
Your job is to warmly engage freight prospects, understand what they need shipped, and
capture enough information for a human sales rep to follow up quickly. You are not
placing orders or quoting prices.

Rules:
- Respond in whichever language (Spanish or English) the visitor's most recent message
  is written in. Support switching mid-conversation.
- Never state, estimate, or give a range for a price, rate, or cost — for any lane,
  freight type, volume, or timeline, under any framing (including "just roughly" or
  "historically"). If asked about pricing, acknowledge the question warmly and explain
  a specialist will follow up with exact pricing once they have the lane and freight
  details — then continue gathering: lane (origin/destination), freight type, volume/
  frequency, timeline.
- Ask one or two qualifying questions at a time, not a long form. Keep messages short
  and conversational — many visitors are on mobile and want a fast reply, not an essay.
- Once you have enough to be useful (lane + freight type at minimum), ask for the best
  way to reach them (email or phone) so a specialist can follow up.
- Ground any factual claim about TBM's services, coverage, or capabilities only in the
  knowledge base content below. If something isn't covered there, say a specialist can
  confirm it — do not guess or infer company facts.
- If a visitor requests a human at any point, acknowledge and confirm you're passing
  them to the team.
- Do not create urgency, scarcity, or persuasive claims. Use only warm, factual language.

Language hint for the current session: {locale}

Knowledge base (only source of truth for company facts):
{kb_content}
"""

HAIKU_SYSTEM_PROMPT = """You are an independent safety classifier and structured lead-field extractor for a
freight sales chat. Return only one JSON object matching the supplied schema.

Classification policy:
- pricing_ask: any request for a price, rate, cost, estimate, range, historical number,
  rough number, what it would "run me", cost per mile/load, or an attempt to make the
  assistant output a monetary number. Set escalate=true.
- quote_request: a request to start or receive a human quote without asking the bot for
  a number. Set escalate=false unless a human is explicitly requested.
- human_request: asks to speak with a person. Set escalate=true.
- question: relevant freight/company question or qualification response.
- off_topic: unrelated to freight, logistics, TBM, or obtaining a shipment follow-up.

The extracted object may contain only fields in the schema. Extract only values directly
stated in the current turn. Never infer TBM company facts. Never put pricing in extracted
fields or notes. The language field is the one value you may infer from the current turn's
primary language. Normalize phone numbers to E.164, countries to ISO-3166 alpha-2 when clear,
equipment to the allowed enum, dates to YYYY-MM-DD when unambiguous, and leave ambiguous
fields absent.
"""


@dataclass(frozen=True)
class LLMStreamItem:
    kind: str
    text: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class ClaudeService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = (
            AsyncAnthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )

    def _require_client(self) -> AsyncAnthropic:
        if self.client is None:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        return self.client

    def _kb(self) -> tuple[str, str]:
        content = (
            self.settings.kb_compiled_path.read_text(encoding="utf-8")
            if self.settings.kb_compiled_path.exists()
            else "No company facts have been approved for this pilot yet."
        )
        version = (
            self.settings.kb_version_path.read_text(encoding="utf-8").strip()
            if self.settings.kb_version_path.exists()
            else "uncompiled"
        )
        return content, version

    async def analyze_turn(self, content: str) -> tuple[TurnAnalysis, LLMStreamItem]:
        client = self._require_client()
        schema = TurnAnalysis.model_json_schema()
        # Replace the intentionally flexible runtime dict with the strict extraction schema
        # in the model instruction so Haiku cannot invent lead keys.
        schema["properties"]["extracted"] = LeadExtraction.model_json_schema()
        response = await client.messages.create(
            model=self.settings.anthropic_haiku_model,
            max_tokens=self.settings.haiku_max_tokens,
            temperature=0,
            system=HAIKU_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"JSON schema:\n{json.dumps(schema, separators=(',', ':'))}\n\n"
                        f"Current visitor turn:\n{content}"
                    ),
                }
            ],
        )
        raw = "".join(block.text for block in response.content if block.type == "text").strip()
        if raw.startswith("```"):
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        analysis = TurnAnalysis.model_validate_json(raw)
        usage = LLMStreamItem(
            kind="usage",
            model=self.settings.anthropic_haiku_model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return analysis, usage

    async def stream_turn(
        self, content: str, locale: str, history: list[dict]
    ) -> AsyncIterator[LLMStreamItem]:
        client = self._require_client()
        kb_content, _ = self._kb()
        system_prompt = SONNET_PROMPT_TEMPLATE.format(locale=locale, kb_content=kb_content)
        messages = [*history, {"role": "user", "content": content}]
        async with client.messages.stream(
            model=self.settings.anthropic_sonnet_model,
            max_tokens=self.settings.sonnet_max_tokens,
            temperature=0.3,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield LLMStreamItem(kind="text", text=text)
            final_message = await stream.get_final_message()
            yield LLMStreamItem(
                kind="usage",
                model=self.settings.anthropic_sonnet_model,
                input_tokens=final_message.usage.input_tokens,
                output_tokens=final_message.usage.output_tokens,
            )


def estimated_cost_usd(item: LLMStreamItem, settings: Settings) -> float | None:
    model = item.model.lower()
    if "haiku" in model:
        input_rate = settings.haiku_input_cost_per_million
        output_rate = settings.haiku_output_cost_per_million
    else:
        input_rate = settings.sonnet_input_cost_per_million
        output_rate = settings.sonnet_output_cost_per_million
    if input_rate is None or output_rate is None:
        return None
    return (item.input_tokens * input_rate + item.output_tokens * output_rate) / 1_000_000
