"""Settings loaded from environment variables (or a .env file).

By default the agent talks to a local Ollama server, so it runs for free.
Point LLM_BASE_URL / LLM_API_KEY / LLM_MODEL at OpenAI or any other
OpenAI-compatible API to use a hosted model instead.
"""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass


DEFAULT_SELLER = (
    "We are a software services company that builds custom software, "
    "AI-powered applications (RAG, AI agents, document processing), "
    "data engineering pipelines and automation for startups and SMEs."
)


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "llama3.1")
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "120"))

    # What YOU sell. The brief is written from this point of view.
    seller_description: str = os.getenv("SELLER_DESCRIPTION", DEFAULT_SELLER)

    # Research limits: keep the agent polite and fast.
    max_extra_pages: int = int(os.getenv("MAX_EXTRA_PAGES", "3"))
    max_chars_per_page: int = int(os.getenv("MAX_CHARS_PER_PAGE", "4000"))
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "15"))
    user_agent: str = os.getenv(
        "USER_AGENT", "LeadResearchAgent/0.1 (+https://github.com/)"
    )

    # LinkedIn connection notes have a character limit; keep it conservative.
    max_note_chars: int = int(os.getenv("MAX_NOTE_CHARS", "200"))


settings = Settings()
