"""Detect technologies a website uses from fingerprints in its HTML.

This is rule-based (no AI), so it is fast, free and predictable.
It only sees front-end and marketing tools, not the backend.
"""

import re

# name -> regex patterns that appear in the HTML when the tool is used
SIGNATURES: dict[str, list[str]] = {
    "Next.js": [r"/_next/static", r"__NEXT_DATA__"],
    "Nuxt": [r"/_nuxt/", r"__NUXT__"],
    "React": [r"data-reactroot", r"react(?:\.production)?(?:\.min)?\.js"],
    "Vue.js": [r"data-v-[0-9a-f]{6,}", r"vue(?:\.min)?\.js"],
    "Angular": [r"ng-version=", r"angular(?:\.min)?\.js"],
    "Gatsby": [r"___gatsby"],
    "WordPress": [r"wp-content/", r"wp-includes/"],
    "Shopify": [r"cdn\.shopify\.com", r"Shopify\.theme"],
    "Webflow": [r"webflow\.(?:js|com)", r"data-wf-page"],
    "Wix": [r"static\.wixstatic\.com", r"wix\.com"],
    "Squarespace": [r"static1\.squarespace\.com", r"squarespace\.com"],
    "HubSpot": [r"js\.hs-scripts\.com", r"js\.hsforms\.net", r"hs-analytics"],
    "Salesforce Pardot": [r"pi\.pardot\.com"],
    "Marketo": [r"munchkin\.marketo\.net"],
    "Google Analytics": [r"googletagmanager\.com/gtag", r"google-analytics\.com"],
    "Google Tag Manager": [r"googletagmanager\.com/gtm\.js"],
    "Segment": [r"cdn\.segment\.com"],
    "Intercom": [r"widget\.intercom\.io", r"intercomSettings"],
    "Drift": [r"js\.driftt\.com"],
    "Zendesk": [r"static\.zdassets\.com", r"zendesk\.com/embeddable"],
    "Stripe": [r"js\.stripe\.com"],
    "Cloudflare": [r"cdnjs\.cloudflare\.com", r"cf-ray", r"/cdn-cgi/"],
}


def detect_tech(html: str) -> list[str]:
    """Return the sorted list of technologies found in the HTML."""
    found = [
        name
        for name, patterns in SIGNATURES.items()
        if any(re.search(p, html, re.IGNORECASE) for p in patterns)
    ]
    return sorted(found)
