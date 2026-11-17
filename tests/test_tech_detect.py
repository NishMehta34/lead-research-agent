from app.tech_detect import detect_tech
from tests.conftest import CAREERS_HTML, HOME_HTML


def test_detects_known_tools():
    assert detect_tech(HOME_HTML) == ["HubSpot", "Next.js"]
    assert detect_tech(CAREERS_HTML) == ["Stripe"]


def test_plain_html_has_no_tech():
    assert detect_tech("<html><body>Hello</body></html>") == []
