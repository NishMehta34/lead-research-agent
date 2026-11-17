from app.agent import fallback_choose_links, research_company
from app.config import Settings
from app.models import Link
from app.report import save_report, to_markdown
from tests.conftest import FakeLLM, fake_fetch


def test_agent_reads_chosen_pages_and_builds_brief(fake_llm):
    result = research_company("acme.test", fake_llm, fetch=fake_fetch)

    assert result.pages_visited == [
        "https://acme.test",
        "https://acme.test/about",
        "https://acme.test/careers",
    ]
    # tech from homepage plus Stripe found on the careers page
    assert result.tech_stack == ["HubSpot", "Next.js", "Stripe"]
    assert result.profile.name == "Acme Logistics"
    assert "Data Engineer" in result.profile.hiring_signals
    assert result.brief.likely_needs


def test_connection_note_is_clipped_to_limit(fake_llm):
    settings = Settings(max_note_chars=120)
    result = research_company("acme.test", fake_llm, fetch=fake_fetch, settings=settings)
    assert len(result.brief.connection_note) <= 120


def test_falls_back_to_keywords_when_llm_choice_is_garbage():
    llm = FakeLLM(choose_reply="I think the about page looks good")
    result = research_company("acme.test", llm, fetch=fake_fetch)
    assert "https://acme.test/about" in result.pages_visited
    assert "https://acme.test/careers" in result.pages_visited


def test_fallback_skips_irrelevant_links():
    links = [Link(url="https://a.test/login", text="Log in"),
             Link(url="https://a.test/about", text="About")]
    assert [l.url for l in fallback_choose_links(links, 3)] == ["https://a.test/about"]


def test_broken_page_is_skipped_not_fatal():
    llm = FakeLLM(choose_reply='{"chosen": [0, 1, 2]}')  # includes /login, which 404s
    result = research_company("acme.test", llm, fetch=fake_fetch)
    assert "https://acme.test/login" not in result.pages_visited


def test_report_is_written(tmp_path, fake_llm):
    result = research_company("acme.test", fake_llm, fetch=fake_fetch)
    md_path, json_path = save_report(result, tmp_path)
    assert md_path.name == "acme-test.md"
    assert json_path.exists()
    assert "# Lead brief: Acme Logistics" in to_markdown(result)
