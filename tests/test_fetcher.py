from app.fetcher import normalise_url, parse_html, same_site
from tests.conftest import HOME_HTML


def test_normalise_url_adds_scheme_and_drops_fragment():
    assert normalise_url("acme.test/about#team") == "https://acme.test/about"
    assert normalise_url("http://acme.test") == "http://acme.test"


def test_same_site_ignores_www():
    assert same_site("https://www.acme.test/a", "https://acme.test/b")
    assert not same_site("https://acme.test", "https://twitter.com/acme")


def test_parse_html_extracts_title_text_and_internal_links():
    page = parse_html("https://acme.test", HOME_HTML)

    assert page.title == "Acme Logistics | Smarter freight"
    assert "Freight management software" in page.text
    assert "should not appear" not in page.text  # scripts removed

    urls = [link.url for link in page.links]
    assert "https://acme.test/about" in urls
    assert "https://acme.test/careers" in urls
    assert not any("twitter.com" in u for u in urls)  # external links dropped
    assert not any(u.startswith("mailto:") for u in urls)
