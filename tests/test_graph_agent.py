"""Tests for the LangGraph loop agent.

The node functions and router are plain Python, so most tests run without
LangGraph. `run_without_langgraph` follows the same edges as `build_graph`.
The last test runs the real compiled graph when LangGraph is installed.
"""

import json
import re

import pytest

from app.config import Settings
from app.graph_agent import make_nodes, route_after_assess
from tests.conftest import FakeLLM, fake_fetch


class LoopLLM(FakeLLM):
    """Reads About first, then follows the team link found on About, then stops."""

    def __init__(self, assess_replies=None):
        super().__init__()
        self.assess_replies = assess_replies

    def chat(self, system, user):
        if "know enough" not in system:
            return super().chat(system, user)
        self.calls.append((system, user))
        if self.assess_replies is not None:
            return self.assess_replies.pop(0)
        links = dict(re.findall(r"^(\d+): .*?-> (\S+)$", user, re.MULTILINE))
        by_url = {url: int(i) for i, url in links.items()}
        for wanted in ("https://acme.test/about", "https://acme.test/team"):
            if wanted in by_url and f"[{wanted}]" not in user:
                return json.dumps({"enough": False, "missing": ["size"],
                                   "next": [by_url[wanted]], "reason": "need more"})
        return json.dumps({"enough": True, "missing": [], "next": [], "reason": "done"})


def run_without_langgraph(llm, settings=Settings()):
    """Follow the same edges as build_graph, using plain Python."""
    nodes = make_nodes(llm, fake_fetch, settings)
    state = {"url": "acme.test"}
    state |= nodes["fetch_homepage"](state)
    while True:
        state |= nodes["assess"](state)
        if route_after_assess(state, settings) == "extract_profile":
            break
        state |= nodes["fetch_more"](state)
    state |= nodes["extract_profile"](state)
    state |= nodes["write_brief"](state)
    return state


def test_loop_follows_links_found_on_later_pages():
    state = run_without_langgraph(LoopLLM())
    urls = [p.url for p in state["pages"]]
    # /team is not linked from the homepage; the agent found it on /about
    assert urls == ["https://acme.test", "https://acme.test/about", "https://acme.test/team"]
    assert state["profile"].name == "Acme Logistics"
    assert any("enough=True" in step for step in state["trace"])


def test_loop_respects_page_limit():
    always_more = [json.dumps({"enough": False, "next": [0, 1]})] * 10
    settings = Settings(max_loop_pages=3, pages_per_round=2)
    state = run_without_langgraph(LoopLLM(always_more), settings)
    assert len(state["pages"]) <= 3


def test_loop_respects_round_limit():
    always_more = [json.dumps({"enough": False, "next": [0]})] * 10
    settings = Settings(max_loop_rounds=2, max_loop_pages=10)
    state = run_without_langgraph(LoopLLM(always_more), settings)
    assert state["rounds"] == 2


def test_bad_assessment_uses_keyword_fallback_once():
    state = run_without_langgraph(LoopLLM(["not json", "still not json"] * 3))
    urls = [p.url for p in state["pages"]]
    assert "https://acme.test/about" in urls
    assert any("keyword fallback" in step for step in state["trace"])


def test_router_stops_when_nothing_chosen():
    state = {"enough": False, "rounds": 1, "pages": [object()], "next_links": []}
    assert route_after_assess(state) == "extract_profile"


def test_real_langgraph_run():
    pytest.importorskip("langgraph")
    from app.graph_agent import research_company_loop

    result = research_company_loop("acme.test", LoopLLM(), fetch=fake_fetch)
    assert result.pages_visited[-1] == "https://acme.test/team"
    assert result.agent_trace
