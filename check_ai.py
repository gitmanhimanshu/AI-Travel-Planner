"""Diagnostic: verify the AI key in .env and list the models it can use.

    python check_ai.py

Free-tier model availability changes over time, so if generation fails with
"model not available", run this and copy a working name into AI_MODEL.
"""

import sys

from app import create_app
from app.services.ai_provider import AIProviderError, detect_provider, get_provider


def main():
    app = create_app()
    with app.app_context():
        key = (app.config.get("AI_API_KEY") or "").strip()
        configured = app.config.get("AI_PROVIDER", "auto")

        print("AI_PROVIDER :", configured)
        print("Key present :", "yes (" + key[:6] + "..." + key[-4:] + ")" if key else "no")
        print("Detected    :", detect_provider(key))
        print("AI_MODEL    :", app.config.get("AI_MODEL") or "(provider default)")
        print("-" * 60)

        try:
            provider = get_provider()
        except AIProviderError as exc:
            print("FAILED to build the provider:", exc)
            return 1

        print("Provider    :", provider.name)
        print("Model       :", getattr(provider, "model", "-"))

        if provider.name == "mock":
            print("\nRunning in demo mode - no API key configured.")
            print("Add AI_API_KEY to your .env to use a real model.")
            return 0

        if provider.name == "gemini":
            _list_gemini_models(provider)

        print("\nSending a one-line test request...")
        try:
            reply = provider.complete_text(
                system="You are a travel assistant. Reply in one short sentence.",
                messages=[{"role": "user", "content": "Name one thing to do in Manali."}],
                max_tokens=200,
            )
            print("OK ->", reply.strip()[:300])
            return 0
        except AIProviderError as exc:
            print("FAILED ->", exc)
            return 1


def _list_gemini_models(provider):
    """Show which models this key may call for text generation."""
    print("\nModels available to this key:")
    try:
        names = []
        for model in provider.client.models.list():
            actions = getattr(model, "supported_actions", None) or []
            if actions and "generateContent" not in actions:
                continue
            names.append((getattr(model, "name", "") or "").replace("models/", ""))
        for name in sorted(set(names)):
            print("  -", name)
        if not names:
            print("  (none returned)")
    except Exception as exc:  # noqa: BLE001 - diagnostics must never crash
        print("  could not list models:", str(exc)[:200])


if __name__ == "__main__":
    sys.exit(main())
