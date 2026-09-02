"""Pluggable AI provider layer.

Everything the rest of the app knows about the LLM lives behind these two
methods:

    complete_json(system, prompt, schema, context)  -> dict
    complete_text(system, messages, context)        -> str

Swapping vendors (or models) means adding one class here and setting
AI_PROVIDER in .env - no route, template or service code changes.
"""

import json
import logging

from flask import current_app

log = logging.getLogger(__name__)

_PROVIDER_CACHE = {}


class AIProviderError(Exception):
    """Raised when the AI backend fails or returns something unusable."""


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class BaseAIProvider:
    name = "base"

    def complete_json(self, system, prompt, schema, context=None, max_tokens=None):
        raise NotImplementedError

    def complete_text(self, system, messages, context=None, max_tokens=1500):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic Claude
# ---------------------------------------------------------------------------
class ClaudeProvider(BaseAIProvider):
    """Claude via the official `anthropic` SDK.

    JSON calls use structured outputs (`output_config.format`), so the model is
    constrained to our itinerary schema instead of being asked politely for
    JSON in the prompt.
    """

    name = "claude"

    def __init__(self, api_key, model, effort="medium", max_tokens=32000, timeout=240.0):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise AIProviderError(
                "The 'anthropic' package is not installed. Run: pip install anthropic"
            ) from exc

        if not api_key:
            raise AIProviderError("AI_API_KEY is not configured.")

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    # -- public API --------------------------------------------------------
    def complete_json(self, system, prompt, schema, context=None, max_tokens=None):
        message = self._send(
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens or self.max_tokens,
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            stream=True,
        )
        text = self._first_text(message)
        try:
            return json.loads(text)
        except (TypeError, ValueError) as exc:
            log.warning("AI returned unparsable JSON: %s", (text or "")[:400])
            raise AIProviderError("The AI response was not valid JSON.") from exc

    def complete_text(self, system, messages, context=None, max_tokens=1500):
        message = self._send(
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            output_config={"effort": "low"},
            stream=False,
        )
        return self._first_text(message)

    # -- internals ---------------------------------------------------------
    def _send(self, system, messages, max_tokens, output_config, stream):
        """Call the Messages API, degrading gracefully when the installed SDK
        or account does not support the optional beta parameters."""
        base_kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "output_config": output_config,
            "thinking": {"type": "adaptive"},
        }
        # Server-side fallbacks keep the app answering if a safety classifier
        # declines a request; harmless to drop if the SDK/account lacks it.
        beta_kwargs = dict(
            base_kwargs, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
        )

        try:
            message = self._invoke(self.client.beta.messages, beta_kwargs, stream)
        except Exception as exc:  # noqa: BLE001 - re-raised as AIProviderError below
            if not self._is_unsupported_param(exc):
                raise self._translate(exc)
            log.info("Retrying without beta parameters: %s", exc)
            try:
                message = self._invoke(self.client.messages, base_kwargs, stream)
            except Exception as inner:  # noqa: BLE001
                raise self._translate(inner)

        if getattr(message, "stop_reason", None) == "refusal":
            raise AIProviderError(
                "The AI declined this request. Please rephrase your trip details."
            )
        return message

    @staticmethod
    def _invoke(endpoint, kwargs, stream):
        if stream:
            with endpoint.stream(**kwargs) as response:
                return response.get_final_message()
        return endpoint.create(**kwargs)

    @staticmethod
    def _first_text(message):
        for block in getattr(message, "content", []) or []:
            if getattr(block, "type", None) == "text" and getattr(block, "text", "").strip():
                return block.text
        raise AIProviderError("The AI returned an empty response.")

    def _is_unsupported_param(self, exc):
        """True when the failure looks like 'this SDK/account rejects betas or
        fallbacks' - the only case worth retrying on the stable endpoint."""
        if isinstance(exc, TypeError):
            return True
        if not isinstance(exc, getattr(self._anthropic, "BadRequestError", ())):
            return False
        text = str(exc).lower()
        markers = (
            "unexpected keyword",
            "unknown parameter",
            "unsupported parameter",
            "not permitted",
            "fallbacks",
            "betas",
        )
        return any(marker in text for marker in markers)

    def _translate(self, exc):
        """Turn SDK exceptions into a message that is safe to show a user."""
        anthropic = self._anthropic
        if isinstance(exc, AIProviderError):
            return exc
        if isinstance(exc, getattr(anthropic, "AuthenticationError", ())):
            return AIProviderError("The AI API key is invalid. Check AI_API_KEY in your .env.")
        if isinstance(exc, getattr(anthropic, "RateLimitError", ())):
            return AIProviderError("The AI service is busy right now. Please try again shortly.")
        if isinstance(exc, getattr(anthropic, "APITimeoutError", ())):
            return AIProviderError("The AI took too long to respond. Please try again.")
        if isinstance(exc, getattr(anthropic, "APIConnectionError", ())):
            return AIProviderError("Could not reach the AI service. Check your connection.")
        if isinstance(exc, getattr(anthropic, "APIStatusError", ())):
            log.exception("AI API error")
            return AIProviderError("The AI service returned an error. Please try again.")
        log.exception("Unexpected AI failure")
        return AIProviderError("Something went wrong while contacting the AI service.")


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------
def _to_gemini_schema(schema):
    """Trim a JSON schema down to what Gemini's structured output accepts.

    Gemini supports a subset of JSON Schema and rejects very large payloads,
    so `additionalProperties` (which it does not need) is stripped throughout.
    """
    if isinstance(schema, dict):
        return {
            key: _to_gemini_schema(value)
            for key, value in schema.items()
            if key != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_to_gemini_schema(item) for item in schema]
    return schema


def _strip_code_fences(text):
    """Some models wrap JSON in ```json fences even in JSON mode."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    return cleaned.strip()


class GeminiProvider(BaseAIProvider):
    """Google Gemini via the official `google-genai` SDK.

    Works on the free Google AI Studio tier. JSON calls use Gemini's structured
    output (`response_mime_type` + `response_schema`); if the model rejects the
    schema, the call retries in plain JSON mode with the schema described in the
    prompt instead - `itinerary_service` normalises either result.
    """

    name = "gemini"
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key, model=None, temperature=0.8, timeout=240.0):
        try:
            from google import genai
            from google.genai import errors as genai_errors
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise AIProviderError(
                "The 'google-genai' package is not installed. Run: pip install google-genai"
            ) from exc

        if not api_key:
            raise AIProviderError("AI_API_KEY is not configured.")

        self._errors = genai_errors
        self.model = model or self.DEFAULT_MODEL
        self.temperature = temperature
        try:
            self.client = genai.Client(
                api_key=api_key, http_options={"timeout": int(timeout * 1000)}
            )
        except TypeError:  # older SDKs without http_options
            self.client = genai.Client(api_key=api_key)

    # -- public API --------------------------------------------------------
    def complete_json(self, system, prompt, schema, context=None, max_tokens=None):
        config = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_schema": _to_gemini_schema(schema),
            "temperature": self.temperature,
        }
        try:
            text = self._call(prompt, config)
        except AIProviderError as exc:
            if not self._is_schema_rejection(exc):
                raise
            log.info("Gemini rejected the response schema; retrying in plain JSON mode.")
            text = self._call(
                prompt
                + "\n\nReturn ONLY a JSON object matching this schema exactly:\n"
                + json.dumps(_to_gemini_schema(schema)),
                {
                    "system_instruction": system,
                    "response_mime_type": "application/json",
                    "temperature": self.temperature,
                },
            )

        try:
            return json.loads(_strip_code_fences(text))
        except (TypeError, ValueError) as exc:
            log.warning("Gemini returned unparsable JSON: %s", (text or "")[:400])
            raise AIProviderError("The AI response was not valid JSON.") from exc

    def complete_text(self, system, messages, context=None, max_tokens=1500):
        contents = [
            {
                "role": "model" if message.get("role") == "assistant" else "user",
                "parts": [{"text": str(message.get("content") or "")}],
            }
            for message in messages
        ]
        # Thinking models spend output tokens before writing a word, so leave
        # generous headroom or the reply comes back empty.
        config = {
            "system_instruction": system,
            "temperature": self.temperature,
            "max_output_tokens": max(4096, max_tokens),
        }
        return self._call(contents, config).strip()

    # -- internals ---------------------------------------------------------
    def _call(self, contents, config):
        # This app never uses tools, so turn off automatic function calling -
        # it also silences a warning the SDK logs on every plain call.
        config = dict(config, automatic_function_calling={"disable": True})
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=contents, config=config
            )
        except Exception as exc:  # noqa: BLE001 - re-raised as AIProviderError
            raise self._translate(exc)
        return self._first_text(response)

    @staticmethod
    def _first_text(response):
        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            raise AIProviderError(
                "Gemini blocked this request. Please rephrase your trip details."
            )

        text = getattr(response, "text", None)
        if text and text.strip():
            return text

        candidates = getattr(response, "candidates", None) or []
        reason = str(getattr(candidates[0], "finish_reason", "")) if candidates else ""
        if "MAX_TOKENS" in reason:
            raise AIProviderError(
                "The AI ran out of output space. Try a shorter trip, or a model "
                "with a larger output limit."
            )
        if "SAFETY" in reason or "RECITATION" in reason:
            raise AIProviderError("Gemini declined to answer that. Please rephrase.")
        raise AIProviderError("The AI returned an empty response.")

    @staticmethod
    def _is_schema_rejection(exc):
        text = str(exc).lower()
        return "schema" in text or "invalid json payload" in text

    def _translate(self, exc):
        """Turn SDK exceptions into a message that is safe to show a user."""
        if isinstance(exc, AIProviderError):
            return exc

        if isinstance(exc, self._errors.APIError):
            code = getattr(exc, "code", None)
            message = str(getattr(exc, "message", "") or exc)
            lowered = message.lower()

            if "api key" in lowered or "api_key" in lowered:
                return AIProviderError(
                    "The Gemini API key is invalid. Check AI_API_KEY in your .env."
                )
            if code in (401, 403):
                return AIProviderError(
                    "Gemini rejected this key. Make sure the Generative Language API "
                    "is enabled for your Google project."
                )
            if code == 404:
                return AIProviderError(
                    "The model '" + self.model + "' is not available for this key. "
                    "Set AI_MODEL in your .env (gemini-2.5-flash is a safe default)."
                )
            if code == 429:
                return AIProviderError(
                    "Gemini's free-tier rate limit was reached. Wait a minute and try again."
                )
            if code and code >= 500:
                return AIProviderError("Gemini is having trouble right now. Please try again.")
            if code == 400 and ("schema" in lowered or "invalid json payload" in lowered):
                return AIProviderError("Gemini rejected the response schema: " + message[:200])
            log.warning("Gemini API error %s: %s", code, message[:300])
            return AIProviderError("Gemini returned an error. Please try again.")

        log.exception("Unexpected Gemini failure")
        return AIProviderError("Something went wrong while contacting Gemini.")


# ---------------------------------------------------------------------------
# Offline demo provider
# ---------------------------------------------------------------------------
class MockProvider(BaseAIProvider):
    """Deterministic sample data so the app is fully usable without an API key."""

    name = "mock"

    ACTIVITY_BANK = [
        (
            "morning",
            "09:00 AM",
            "Local sightseeing walk",
            "Ease into the day with the most photogenic streets and a slow breakfast.",
        ),
        (
            "afternoon",
            "01:30 PM",
            "Signature experience",
            "The one activity people remember this place for - book ahead to skip the queue.",
        ),
        (
            "evening",
            "07:00 PM",
            "Sunset point and local dinner",
            "Watch the light go, then eat where the locals eat.",
        ),
    ]

    def complete_json(self, system, prompt, schema, context=None, max_tokens=None):
        context = context or {}
        kind = context.get("kind", "itinerary")
        if kind == "packing":
            return {
                "packing_list": self._packing(context),
                "notes": "Sample list - add an AI_API_KEY for a tailored one.",
            }
        if kind == "budget":
            return self._budget_options(context)
        return self._itinerary(context)

    def complete_text(self, system, messages, context=None, max_tokens=1500):
        question = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                question = str(message.get("content", ""))
                break
        return (
            "I am running in demo mode without an AI key, so here is a general answer. "
            "About " + question[:120] + " - start with the neighbourhood around your stay and "
            "ask your host for two options, one cheap and one special. "
            "Set AI_API_KEY in your .env to get real, trip-aware answers."
        )

    # -- generators --------------------------------------------------------
    def _itinerary(self, ctx):
        destination = ctx.get("destination") or "Your destination"
        days = max(1, int(ctx.get("duration_days") or 3))
        travelers = max(1, int(ctx.get("travelers") or 1))
        budget = float(ctx.get("budget_amount") or 0) or days * travelers * 4500.0

        per_day = round(budget * 0.45 / days)
        transport = round(budget * 0.20)
        stay = round(budget * 0.25)
        food = round(budget * 0.20)
        activities = round(budget * 0.20)
        misc = max(0, round(budget - transport - stay - food - activities))

        day_list = []
        for index in range(1, days + 1):
            day_list.append(
                {
                    "day": index,
                    "title": "Day " + str(index) + " in " + destination,
                    "location": destination,
                    "activities": [
                        {
                            "period": period,
                            "time": time,
                            "activity": title + " (" + destination + ")",
                            "description": description,
                            "estimated_cost": round(per_day / 3),
                        }
                        for period, time, title, description in self.ACTIVITY_BANK
                    ],
                    "food_recommendations": [
                        {
                            "name": "A well-reviewed local kitchen",
                            "dish": "The regional speciality",
                            "approx_cost": 400,
                        }
                    ],
                    "estimated_cost": per_day,
                }
            )

        return {
            "trip_summary": {
                "destination": destination,
                "duration": str(days) + " Days",
                "estimated_budget": round(budget),
                "best_time": "October - March",
                "overview": (
                    "A sample " + str(days) + "-day plan for " + destination
                    + ". Add an AI key for a fully personalised itinerary."
                ),
            },
            "transportation": {
                "recommendation": (
                    "Travel from " + str(ctx.get("start_location") or "your city")
                    + " by " + str(ctx.get("transportation") or "train")
                    + "; book two weeks ahead for the best fares."
                ),
                "estimated_cost": transport,
                "tips": ["Book early", "Travel light on transfer days"],
            },
            "accommodation": {
                "recommendation": (
                    "A centrally located " + str(ctx.get("accommodation") or "hotel")
                    + " keeps daily travel short."
                ),
                "estimated_cost": stay,
                "suggestions": [
                    {
                        "name": "Central stay",
                        "type": str(ctx.get("accommodation") or "Hotel"),
                        "area": "City centre",
                        "approx_cost_per_night": round(stay / days),
                    }
                ],
            },
            "days": day_list,
            "restaurants": [
                {
                    "name": "The local favourite",
                    "cuisine": "Regional",
                    "area": "Old town",
                    "price_range": "Moderate",
                    "must_try": "Whatever is on the day's board",
                }
            ],
            "places_to_visit": [
                {
                    "name": destination + " viewpoint",
                    "description": "The classic first stop.",
                    "best_time_to_visit": "Early morning",
                    "entry_fee": "Free",
                    "map_query": destination + " viewpoint",
                }
            ],
            "budget_breakdown": {
                "transport": transport,
                "accommodation": stay,
                "food": food,
                "activities": activities,
                "miscellaneous": misc,
                "total": round(transport + stay + food + activities + misc),
            },
            "travel_tips": [
                "Carry some cash - small vendors often do not take cards.",
                "Keep one buffer day in case the weather turns.",
            ],
            "packing_list": self._packing(ctx),
            "budget_alert": {
                "over_budget": False,
                "message": "This sample plan fits the budget you entered.",
                "cheaper_alternatives": [],
            },
        }

    def _packing(self, ctx):
        base = [
            "Photo ID and travel tickets",
            "Power bank and charger",
            "Reusable water bottle",
            "Basic medicines",
            "Weather-appropriate layers",
        ]
        interests = [str(item).lower() for item in (ctx.get("interests") or [])]
        if "trekking" in interests or "mountains" in interests:
            base += ["Trekking shoes", "Warm jacket"]
        if "beaches" in interests:
            base += ["Sunscreen", "Swimwear"]
        if "photography" in interests:
            base += ["Spare memory card", "Lens cloth"]
        return base

    def _budget_options(self, ctx):
        target = float(ctx.get("target_budget") or 0) or 20000.0
        return {
            "optimized_total": round(target * 0.85),
            "savings": round(target * 0.15),
            "suggestions": [
                {
                    "area": "Accommodation",
                    "change": "Swap the hotel for a homestay two streets back.",
                    "saving": round(target * 0.07),
                },
                {
                    "area": "Transport",
                    "change": "Take the overnight train instead of flying.",
                    "saving": round(target * 0.05),
                },
                {
                    "area": "Activities",
                    "change": "Pick two paid experiences instead of four.",
                    "saving": round(target * 0.03),
                },
            ],
            "summary": "Demo suggestions - configure AI_API_KEY for a plan-specific optimisation.",
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def detect_provider(api_key):
    """Guess the vendor from the key's own prefix.

    Google AI Studio keys start with "AIza"; Anthropic keys with "sk-ant-".
    Anything else has to be named explicitly via AI_PROVIDER.
    """
    key = (api_key or "").strip()
    if not key:
        return "mock"
    if key.startswith("AIza"):
        return "gemini"
    if key.startswith("sk-ant-"):
        return "claude"
    return "unknown"


def get_provider():
    """Return the configured provider, built once per process."""
    config = current_app.config
    choice = (config.get("AI_PROVIDER") or "auto").lower()
    api_key = (config.get("AI_API_KEY") or "").strip()
    model = config.get("AI_MODEL") or None

    if choice == "auto":
        choice = detect_provider(api_key)
        if choice == "unknown":
            raise AIProviderError(
                "Could not tell which AI service that key belongs to. "
                "Set AI_PROVIDER=gemini or AI_PROVIDER=claude in your .env."
            )

    cache_key = (choice, model, bool(api_key))
    if cache_key in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[cache_key]

    if choice == "gemini":
        provider = GeminiProvider(
            api_key=api_key,
            model=model,
            temperature=config.get("AI_TEMPERATURE", 0.8),
            timeout=config.get("AI_TIMEOUT_SECONDS", 240.0),
        )
    elif choice == "claude":
        provider = ClaudeProvider(
            api_key=api_key,
            model=model or "claude-opus-5",
            effort=config.get("AI_EFFORT", "medium"),
            max_tokens=config.get("AI_MAX_TOKENS", 32000),
            timeout=config.get("AI_TIMEOUT_SECONDS", 240.0),
        )
    elif choice == "mock":
        provider = MockProvider()
    else:
        raise AIProviderError(
            "Unknown AI_PROVIDER '" + choice + "'. Use 'gemini', 'claude', 'mock' or 'auto'."
        )

    _PROVIDER_CACHE[cache_key] = provider
    return provider


def provider_is_live():
    """True when a real model is configured (used for the demo-mode banner)."""
    try:
        return get_provider().name != "mock"
    except AIProviderError:
        return False
