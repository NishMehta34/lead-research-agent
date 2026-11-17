"""Data models shared by the agent, the CLI and the API."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Link(BaseModel):
    url: str
    text: str = ""


class PageContent(BaseModel):
    url: str
    title: str = ""
    text: str = ""
    links: list[Link] = Field(default_factory=list)
    html: str = Field(default="", exclude=True)  # kept for tech detection, not exported


class CompanyProfile(BaseModel):
    name: str = ""
    what_they_do: str = ""
    products_or_services: list[str] = Field(default_factory=list)
    target_customers: str = ""
    size_signals: str = ""
    hiring_signals: list[str] = Field(default_factory=list)


class SalesBrief(BaseModel):
    summary: str = ""
    likely_needs: list[str] = Field(default_factory=list)
    conversation_starters: list[str] = Field(default_factory=list)
    connection_note: str = ""
    follow_up_message: str = ""


class ResearchResult(BaseModel):
    url: str
    profile: CompanyProfile
    tech_stack: list[str] = Field(default_factory=list)
    pages_visited: list[str] = Field(default_factory=list)
    brief: SalesBrief
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
