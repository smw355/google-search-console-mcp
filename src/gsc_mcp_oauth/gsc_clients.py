"""HTTP client helpers for GSC REST APIs.

All GSC API calls use direct httpx REST requests rather than the google-api-python-client
library. This avoids file-based credential flows and works with bare OAuth access tokens.
"""

import urllib.parse

WEBMASTERS_V3 = "https://www.googleapis.com/webmasters/v3"
SEARCH_CONSOLE_V1 = "https://searchconsole.googleapis.com/v1"


def auth_headers(token: str) -> dict[str, str]:
    """Returns the Authorization header dict for a bearer token."""
    return {"Authorization": f"Bearer {token}"}


def encode_site(site_url: str) -> str:
    """URL-encode a site URL for use in REST path segments.

    GSC site URLs include slashes (https://example.com/) and must be
    percent-encoded when embedded in API path segments.
    Example: "https://example.com/" -> "https%3A%2F%2Fexample.com%2F"
    """
    return urllib.parse.quote(site_url, safe="")


def encode_feedpath(feedpath: str) -> str:
    """URL-encode a sitemap feedpath for use in REST path segments."""
    return urllib.parse.quote(feedpath, safe="")
