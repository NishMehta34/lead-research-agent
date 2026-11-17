"""Turn a ResearchResult into a Markdown brief and save it to disk."""

import re
from pathlib import Path
from urllib.parse import urlparse

from app.models import ResearchResult


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (none found)"


def to_markdown(result: ResearchResult) -> str:
    p, b = result.profile, result.brief
    return f"""# Lead brief: {p.name or result.url}

**Website:** {result.url}
**Generated:** {result.generated_at}

## Summary
{b.summary}

## Company profile
**What they do:** {p.what_they_do}

**Products / services:**
{_bullets(p.products_or_services)}

**Target customers:** {p.target_customers or "(not stated)"}

**Size / stage signals:** {p.size_signals or "(not stated)"}

**Hiring signals:**
{_bullets(p.hiring_signals)}

**Website tech detected:** {", ".join(result.tech_stack) or "none detected"}

## Likely needs
{_bullets(b.likely_needs)}

## Conversation starters
{_bullets(b.conversation_starters)}

## Outreach drafts
**Connection note** ({len(b.connection_note)} chars):
> {b.connection_note}

**Follow-up after they accept:**
> {b.follow_up_message}

---
Pages read: {", ".join(result.pages_visited)}

*AI-generated from public website content. Check facts before sending anything.*
"""


def slug_for(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return re.sub(r"[^a-z0-9]+", "-", host).strip("-") or "company"


def save_report(result: ResearchResult, folder: str | Path = "reports") -> tuple[Path, Path]:
    """Write <slug>.md and <slug>.json; return both paths."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    slug = slug_for(result.url)
    md_path = folder / f"{slug}.md"
    json_path = folder / f"{slug}.json"
    md_path.write_text(to_markdown(result), encoding="utf-8")
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return md_path, json_path
