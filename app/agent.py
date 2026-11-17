"""The research agent.

Steps:
  1. Fetch the homepage.
  2. Detect the front-end tech stack from the HTML (rules, no AI).
  3. AGENT DECISION: the LLM chooses which other pages are worth reading.
  4. Fetch those pages.
  5. The LLM extracts a structured company profile from the text.
  6. The LLM writes a sales brief from the profile and our own offering.

Step 3 is what makes this an agent rather than a fixed script: the model
decides where to look next based on what it found on the homepage.
"""

import logging
from typing import Callable

from app.config import Settings, settings as default_settings
from app.fetcher import fetch_page, normalise_url
from app.llm import ChatModel, chat_json
from app.models import CompanyProfile, Link, PageContent, ResearchResult, SalesBrief
from app.prompts import (
    BRIEF_SYSTEM,
    BRIEF_USER,
    CHOOSE_PAGES_SYSTEM,
    CHOOSE_PAGES_USER,
    PROFILE_SYSTEM,
    PROFILE_USER,
)
from app.tech_detect import detect_tech

log = logging.getLogger(__name__)

Fetcher = Callable[[str], PageContent]

# Used when the model's page choice can't be parsed.
_USEFUL_WORDS = [
    "about", "company", "product", "platform", "solution", "service",
    "customer", "case-stud", "careers", "jobs", "pricing", "team",
]


def fallback_choose_links(links: list[Link], max_pages: int) -> list[Link]:
    """Pick links whose URL or text contains a useful keyword."""
    scored = []
    for link in links:
        haystack = (link.url + " " + link.text).lower()
        score = sum(word in haystack for word in _USEFUL_WORDS)
        if score:
            scored.append((score, link))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [link for _, link in scored[:max_pages]]


def choose_links(llm: ChatModel, url: str, links: list[Link], max_pages: int) -> list[Link]:
    """Let the LLM decide which pages to read next."""
    if not links or max_pages <= 0:
        return []
    candidates = links[:60]  # keep the prompt small
    listing = "\n".join(f"{i}: {l.text or '(no text)'} -> {l.url}" for i, l in enumerate(candidates))
    try:
        data = chat_json(
            llm,
            CHOOSE_PAGES_SYSTEM,
            CHOOSE_PAGES_USER.format(url=url, links=listing, max_pages=max_pages),
        )
        chosen = []
        for index in data.get("chosen", []):
            if isinstance(index, int) and 0 <= index < len(candidates):
                if candidates[index] not in chosen:
                    chosen.append(candidates[index])
        if chosen:
            log.info("Agent chose pages: %s", data.get("reason", ""))
            return chosen[:max_pages]
    except Exception as exc:  # bad JSON, model error, etc.
        log.warning("Page choice failed (%s); using keyword fallback", exc)
    return fallback_choose_links(candidates, max_pages)


def _format_pages(pages: list[PageContent], max_chars: int) -> str:
    return "\n\n".join(
        f"--- PAGE: {p.url} ({p.title}) ---\n{p.text[:max_chars]}" for p in pages
    )


def _clip(text: str, limit: int) -> str:
    """Trim to `limit` characters on a word boundary."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def research_company(
    url: str,
    llm: ChatModel,
    fetch: Fetcher = fetch_page,
    settings: Settings = default_settings,
) -> ResearchResult:
    url = normalise_url(url)

    # 1-2. Homepage and tech stack
    homepage = fetch(url)
    tech = detect_tech(homepage.html)

    # 3-4. Let the agent pick and read more pages
    pages = [homepage]
    for link in choose_links(llm, url, homepage.links, settings.max_extra_pages):
        try:
            page = fetch(link.url)
            pages.append(page)
            for name in detect_tech(page.html):  # careers pages often reveal more
                if name not in tech:
                    tech.append(name)
        except Exception as exc:
            log.warning("Skipping %s: %s", link.url, exc)
    tech.sort()

    # 5. Structured profile
    profile_data = chat_json(
        llm,
        PROFILE_SYSTEM,
        PROFILE_USER.format(url=url, pages=_format_pages(pages, settings.max_chars_per_page)),
    )
    profile = CompanyProfile.model_validate(profile_data)

    # 6. Sales brief
    brief_data = chat_json(
        llm,
        BRIEF_SYSTEM,
        BRIEF_USER.format(
            seller=settings.seller_description,
            profile=profile.model_dump_json(indent=2),
            tech=", ".join(tech) or "none detected",
            max_note=settings.max_note_chars,
        ),
    )
    brief = SalesBrief.model_validate(brief_data)
    brief.connection_note = _clip(brief.connection_note, settings.max_note_chars)

    return ResearchResult(
        url=url,
        profile=profile,
        tech_stack=tech,
        pages_visited=[p.url for p in pages],
        brief=brief,
    )
