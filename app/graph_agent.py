"""Loop agent built with LangGraph.

The simple agent (agent.py) reads a fixed number of pages chosen once from
the homepage. This one works in a loop:

    fetch_homepage -> assess --(enough?)--> extract_profile -> write_brief -> END
                        ^          |
                        |       (not yet)
                        |          v
                        +----- fetch_more

`assess` asks the LLM what is still unknown and which page to read next.
`fetch_more` reads those pages and adds any new links it finds, so the
agent can follow a trail (homepage -> about -> team page).

The loop always ends: `route_after_assess` stops it when the LLM says it
has enough, when the page or round limit is hit, or when no links remain.

The node functions are plain Python, so they can be tested without
LangGraph installed. Only `build_graph` imports LangGraph.
"""

import logging
from typing import TypedDict

from app.agent import (
    Fetcher,
    extract_profile,
    fallback_choose_links,
    merge_tech,
    write_brief,
)
from app.config import Settings, settings as default_settings
from app.fetcher import fetch_page, normalise_url
from app.llm import ChatModel, chat_json
from app.models import CompanyProfile, Link, PageContent, ResearchResult, SalesBrief
from app.prompts import ASSESS_SYSTEM, ASSESS_USER

log = logging.getLogger(__name__)


class LoopState(TypedDict, total=False):
    url: str
    pages: list[PageContent]  # pages read so far, homepage first
    candidates: list[Link]  # unread same-site links
    next_links: list[Link]  # what assess chose to read next
    tech: list[str]
    enough: bool
    rounds: int
    trace: list[str]  # human-readable log of the agent's decisions
    profile: CompanyProfile
    brief: SalesBrief


def _add_candidates(candidates: list[Link], new: list[Link], visited: set[str]) -> list[Link]:
    """Append links we haven't seen or read yet."""
    known = {link.url for link in candidates} | visited
    merged = list(candidates)
    for link in new:
        if link.url not in known:
            merged.append(link)
            known.add(link.url)
    return merged


def _page_digest(pages: list[PageContent], chars: int = 1500) -> str:
    return "\n\n".join(f"[{p.url}] {p.title}\n{p.text[:chars]}" for p in pages)


def make_nodes(llm: ChatModel, fetch: Fetcher, settings: Settings) -> dict:
    """Create the graph's node functions with their dependencies baked in."""

    def fetch_homepage(state: LoopState) -> LoopState:
        url = normalise_url(state["url"])
        home = fetch(url)
        return {
            "url": url,
            "pages": [home],
            "candidates": _add_candidates([], home.links, {url}),
            "tech": merge_tech([], home.html),
            "rounds": 0,
            "enough": False,
            "next_links": [],
            "trace": [f"Read homepage {url} ({len(home.links)} links found)"],
        }

    def assess(state: LoopState) -> LoopState:
        pages, candidates = state["pages"], state["candidates"][:60]
        remaining = settings.max_loop_pages - len(pages)
        max_next = min(settings.pages_per_round, remaining)
        trace = list(state["trace"])
        rounds = state["rounds"] + 1

        if remaining <= 0 or not candidates:
            trace.append(f"Round {rounds}: no more pages allowed or available, stopping")
            return {"enough": True, "next_links": [], "rounds": rounds, "trace": trace}

        listing = "\n".join(
            f"{i}: {l.text or '(no text)'} -> {l.url}" for i, l in enumerate(candidates)
        )
        try:
            data = chat_json(
                llm,
                ASSESS_SYSTEM,
                ASSESS_USER.format(
                    url=state["url"],
                    pages=_page_digest(pages),
                    links=listing,
                    max_next=max_next,
                    remaining=remaining,
                ),
            )
            enough = bool(data.get("enough"))
            chosen = []
            for i in data.get("next", []):
                if isinstance(i, int) and 0 <= i < len(candidates) and candidates[i] not in chosen:
                    chosen.append(candidates[i])
            chosen = chosen[:max_next]
            missing = ", ".join(data.get("missing", [])) or "nothing"
            trace.append(
                f"Round {rounds}: enough={enough}; missing: {missing}; "
                f"next: {[l.url for l in chosen] or 'none'}. {data.get('reason', '')}".strip()
            )
            if not enough and not chosen:  # model wants more but picked nothing usable
                enough = True
        except Exception as exc:
            # Unusable reply: read keyword-matched pages once, then stop.
            chosen = fallback_choose_links(candidates, max_next) if len(pages) == 1 else []
            enough = not chosen
            trace.append(f"Round {rounds}: assessment failed ({exc}); keyword fallback")

        return {"enough": enough, "next_links": chosen, "rounds": rounds, "trace": trace}

    def fetch_more(state: LoopState) -> LoopState:
        pages = list(state["pages"])
        visited = {p.url for p in pages}
        candidates = list(state["candidates"])
        tech = list(state["tech"])
        trace = list(state["trace"])

        for link in state["next_links"]:
            candidates = [c for c in candidates if c.url != link.url]
            visited.add(link.url)
            try:
                page = fetch(link.url)
            except Exception as exc:
                trace.append(f"  could not read {link.url}: {exc}")
                continue
            pages.append(page)
            tech = merge_tech(tech, page.html)
            candidates = _add_candidates(candidates, page.links, visited)
            trace.append(f"  read {link.url}")

        return {"pages": pages, "candidates": candidates, "tech": tech,
                "next_links": [], "trace": trace}

    def extract(state: LoopState) -> LoopState:
        return {"profile": extract_profile(llm, state["url"], state["pages"], settings)}

    def brief(state: LoopState) -> LoopState:
        return {"brief": write_brief(llm, state["profile"], state["tech"], settings)}

    return {
        "fetch_homepage": fetch_homepage,
        "assess": assess,
        "fetch_more": fetch_more,
        "extract_profile": extract,
        "write_brief": brief,
    }


def route_after_assess(state: LoopState, settings: Settings = default_settings) -> str:
    """Decide whether to keep reading or start writing. Guarantees the loop ends."""
    if state.get("enough"):
        return "extract_profile"
    if state["rounds"] >= settings.max_loop_rounds:
        return "extract_profile"
    if len(state["pages"]) >= settings.max_loop_pages:
        return "extract_profile"
    if not state.get("next_links"):
        return "extract_profile"
    return "fetch_more"


def build_graph(llm: ChatModel, fetch: Fetcher = fetch_page, settings: Settings = default_settings):
    """Wire the nodes into a LangGraph state machine and compile it."""
    from langgraph.graph import END, START, StateGraph

    nodes = make_nodes(llm, fetch, settings)
    graph = StateGraph(LoopState)
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    graph.add_edge(START, "fetch_homepage")
    graph.add_edge("fetch_homepage", "assess")
    graph.add_conditional_edges(
        "assess",
        lambda state: route_after_assess(state, settings),
        {"fetch_more": "fetch_more", "extract_profile": "extract_profile"},
    )
    graph.add_edge("fetch_more", "assess")
    graph.add_edge("extract_profile", "write_brief")
    graph.add_edge("write_brief", END)
    return graph.compile()


def research_company_loop(
    url: str,
    llm: ChatModel,
    fetch: Fetcher = fetch_page,
    settings: Settings = default_settings,
) -> ResearchResult:
    graph = build_graph(llm, fetch, settings)
    # Each round is 2 graph steps; leave plenty of headroom.
    final = graph.invoke({"url": url}, config={"recursion_limit": 4 * settings.max_loop_rounds + 10})
    return ResearchResult(
        url=final["url"],
        profile=final["profile"],
        tech_stack=final["tech"],
        pages_visited=[p.url for p in final["pages"]],
        brief=final["brief"],
        agent_trace=final["trace"],
    )
