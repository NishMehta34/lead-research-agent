"""Shared test fixtures: a fake website and a fake LLM, so tests need no network."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fetcher import parse_html  # noqa: E402

HOME_HTML = """
<html><head><title>Acme Logistics | Smarter freight</title>
<script src="/_next/static/chunks/main.js"></script>
<script src="https://js.hs-scripts.com/123.js"></script>
</head><body>
<nav><a href="/about">About us</a> <a href="/careers">Careers</a>
<a href="/login">Log in</a> <a href="https://twitter.com/acme">Twitter</a>
<a href="mailto:hi@acme.test">Email</a></nav>
<h1>Freight management software for mid-sized shippers</h1>
<p>Acme helps 300 shippers plan routes and track loads.</p>
<script>var secret = "should not appear in text";</script>
</body></html>
"""

ABOUT_HTML = """<html><head><title>About Acme</title></head><body>
<p>Founded in 2019, 45 people across London and Austin.</p></body></html>"""

CAREERS_HTML = """<html><head><title>Careers</title>
<script src="https://js.stripe.com/v3"></script></head><body>
<p>We're hiring a Senior Python Engineer and a Data Engineer.</p></body></html>"""

SITE = {
    "https://acme.test": HOME_HTML,
    "https://acme.test/about": ABOUT_HTML,
    "https://acme.test/careers": CAREERS_HTML,
}


def fake_fetch(url: str):
    url = url.rstrip("/")
    if url not in SITE:
        raise ConnectionError(f"404 {url}")
    return parse_html(url, SITE[url])


class FakeLLM:
    """Returns canned replies based on which prompt it receives, and records calls."""

    def __init__(self, choose_reply=None):
        self.calls = []
        self.choose_reply = choose_reply

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if "choose which pages" in system:
            if self.choose_reply is not None:
                return self.choose_reply
            # find the numbers for About and Careers in the listing
            chosen = [
                int(line.split(":")[0])
                for line in user.splitlines()
                if ("About" in line or "Careers" in line) and line[:1].isdigit()
            ]
            return json.dumps({"chosen": chosen, "reason": "about + careers"})
        if "extract facts" in system:
            return "```json\n" + json.dumps({
                "name": "Acme Logistics",
                "what_they_do": "Freight management software for mid-sized shippers.",
                "products_or_services": ["Route planning", "Load tracking"],
                "target_customers": "Mid-sized shippers",
                "size_signals": "45 people, offices in London and Austin",
                "hiring_signals": ["Senior Python Engineer", "Data Engineer"],
            }) + "\n```"
        return "Here you go: " + json.dumps({
            "summary": "Growing freight SaaS hiring data roles.",
            "likely_needs": ["Data pipeline capacity", "AI route optimisation"],
            "conversation_starters": ["How are you handling load-tracking data today?"],
            "connection_note": "Hi! " + "Interesting work on freight software. " * 20,
            "follow_up_message": "Thanks for connecting.",
        })


@pytest.fixture
def fake_llm():
    return FakeLLM()
