"""Fetch web pages and turn HTML into clean text plus a list of links.

`parse_html` is a pure function (no network), which makes it easy to test.
`fetch_page` does the HTTP request and then calls `parse_html`.
"""

import re
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from app.config import settings
from app.models import Link, PageContent

# Tags that never contain useful company information.
_NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "form"]


def normalise_url(url: str) -> str:
    """Add https:// if missing and strip #fragments."""
    url = url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return urldefrag(url)[0]


def same_site(url_a: str, url_b: str) -> bool:
    """True if both URLs are on the same domain (ignoring 'www.')."""
    host_a = urlparse(url_a).netloc.lower().removeprefix("www.")
    host_b = urlparse(url_b).netloc.lower().removeprefix("www.")
    return host_a == host_b


def parse_html(url: str, html: str) -> PageContent:
    """Extract title, readable text and same-site links from raw HTML."""
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else ""

    # Collect links before removing anything, so nav/footer links are kept.
    links: list[Link] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = urldefrag(urljoin(url, href))[0].rstrip("/")
        if not same_site(url, absolute) or absolute in seen or absolute == url.rstrip("/"):
            continue
        seen.add(absolute)
        links.append(Link(url=absolute, text=a.get_text(" ", strip=True)[:80]))

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    return PageContent(url=url, title=title, text=text, links=links, html=html)


def allowed_by_robots(url: str) -> bool:
    """Respect robots.txt. If robots.txt can't be read, assume allowed."""
    parts = urlparse(url)
    robots = RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        robots.read()
    except Exception:
        return True
    return robots.can_fetch(settings.user_agent, url)


def fetch_page(url: str) -> PageContent:
    """Download one page and parse it. Raises on HTTP errors."""
    import httpx  # imported here so tests can run without network libraries

    url = normalise_url(url)
    if not allowed_by_robots(url):
        raise PermissionError(f"robots.txt does not allow fetching {url}")

    response = httpx.get(
        url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    return parse_html(str(response.url), response.text)
