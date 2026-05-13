from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv


load_dotenv()

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash-lite",
    "groq": "openai/gpt-oss-20b",
    "openai": "gpt-4.1-mini",
    "openrouter": "openai/gpt-oss-120b:free",
}


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "gemini").strip().lower()


def _model_name(provider: str) -> str:
    return os.getenv("MODEL_NAME", DEFAULT_MODELS[provider]).strip()


def create_chat_model(**overrides: Any):
    provider = _provider()
    if provider not in DEFAULT_MODELS:
        supported = ", ".join(sorted(DEFAULT_MODELS))
        raise ValueError(f"Unsupported LLM_PROVIDER={provider!r}. Use one of: {supported}")

    model = _model_name(provider)
    temperature = float(os.getenv("MODEL_TEMPERATURE", "0"))
    common = {"model": model, "temperature": temperature, **overrides}

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(**common)

    if provider == "groq":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            **common,
            api_key=os.getenv("GROQ_API_KEY"),
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )

    if provider == "openrouter":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            **common,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8501"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "TailorTalk Drive Search"),
            },
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(**common, api_key=os.getenv("OPENAI_API_KEY"))
