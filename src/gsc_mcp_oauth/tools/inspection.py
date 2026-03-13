"""URL inspection tools: inspect, batch inspect, indexing issues, performance overview."""

import json
import logging
from datetime import date, timedelta

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken

from gsc_mcp_oauth.gsc_clients import (
    SEARCH_CONSOLE_V1,
    WEBMASTERS_V3,
    auth_headers,
    encode_site,
)

logger = logging.getLogger(__name__)

_MAX_BATCH_URLS = 10


def _classify_url_result(inspection_url: str, result: dict) -> str:
    """Categorizes a URL inspection result into an issue type."""
    index_result = result.get("inspectionResult", {}).get("indexStatusResult", {})
    verdict = index_result.get("verdict", "")
    robots_txt_state = index_result.get("robotsTxtState", "")
    indexing_state = index_result.get("indexingState", "")
    page_fetch_state = index_result.get("pageFetchState", "")
    google_canonical = index_result.get("googleCanonical", "")

    if verdict == "PASS":
        return "indexed"
    if robots_txt_state == "DISALLOWED" or "ROBOTS_TXT" in indexing_state:
        return "robots_blocked"
    if google_canonical and google_canonical != inspection_url:
        return "canonical_mismatch"
    if page_fetch_state and page_fetch_state != "SUCCESSFUL":
        return "fetch_errors"
    if verdict == "FAIL":
        return "not_indexed"
    return "unknown"


def register_inspection_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="gsc_inspect_url",
        annotations={
            "title": "Inspect URL Indexing Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_inspect_url(
        site_url: str,
        page_url: str,
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Inspects a URL's indexing status using the Google Search Console URL Inspection API.

        Returns detailed information about how Google sees the URL, including
        indexing status, canonical URL, crawl state, robots.txt blocking, and
        rich results detection.

        Args:
            site_url: The GSC property URL that owns the page
                      (e.g. "https://example.com/"). Must be verified in GSC.
            page_url: The specific URL to inspect
                      (e.g. "https://example.com/blog/post/").

        Returns:
            str: JSON object with full inspection result including indexStatusResult
                 and richResultsResult fields.
        """
        try:
            body = {"inspectionUrl": page_url, "siteUrl": site_url}
            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.post(
                    f"{SEARCH_CONSOLE_V1}/urlInspection/index:inspect",
                    json=body,
                )
                resp.raise_for_status()
                return json.dumps(resp.json(), indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_inspect_url failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_inspect_url failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_batch_inspect_urls",
        annotations={
            "title": "Batch Inspect Multiple URLs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_batch_inspect_urls(
        site_url: str,
        urls: list[str],
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Inspects up to 10 URLs and returns their indexing status with a summary.

        Makes individual inspection calls sequentially to avoid rate limit issues.

        Args:
            site_url: The GSC property URL that owns the pages.
            urls: List of 1–10 URLs to inspect.

        Returns:
            str: JSON object with "results" (list of inspection outcomes) and
                 "summary" (counts of indexed, not_indexed, errors).
        """
        if len(urls) > _MAX_BATCH_URLS:
            return json.dumps({
                "error": f"Maximum {_MAX_BATCH_URLS} URLs per batch. Received {len(urls)}."
            })

        try:
            results = []
            indexed = 0
            not_indexed = 0
            errors = 0

            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                for url in urls:
                    try:
                        resp = await client.post(
                            f"{SEARCH_CONSOLE_V1}/urlInspection/index:inspect",
                            json={"inspectionUrl": url, "siteUrl": site_url},
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        verdict = (
                            data.get("inspectionResult", {})
                            .get("indexStatusResult", {})
                            .get("verdict", "VERDICT_UNSPECIFIED")
                        )
                        results.append({"url": url, "result": data})
                        if verdict == "PASS":
                            indexed += 1
                        else:
                            not_indexed += 1
                    except Exception as url_err:
                        logger.exception("gsc_batch_inspect_urls: failed for %s", url)
                        results.append({"url": url, "error": str(url_err)})
                        errors += 1

            return json.dumps({
                "results": results,
                "summary": {
                    "total": len(urls),
                    "indexed": indexed,
                    "not_indexed": not_indexed,
                    "errors": errors,
                },
            }, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_batch_inspect_urls failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_batch_inspect_urls failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_check_indexing_issues",
        annotations={
            "title": "Check Indexing Issues for Multiple URLs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_check_indexing_issues(
        site_url: str,
        urls: list[str],
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Inspects up to 10 URLs and categorizes them by their indexing issue type.

        Categories: indexed, not_indexed, robots_blocked, canonical_mismatch,
        fetch_errors, unknown.

        Args:
            site_url: The GSC property URL that owns the pages.
            urls: List of 1–10 URLs to check.

        Returns:
            str: JSON object with lists of URLs grouped by issue category.
        """
        if len(urls) > _MAX_BATCH_URLS:
            return json.dumps({
                "error": f"Maximum {_MAX_BATCH_URLS} URLs per batch. Received {len(urls)}."
            })

        try:
            categories: dict[str, list[str]] = {
                "indexed": [],
                "not_indexed": [],
                "robots_blocked": [],
                "canonical_mismatch": [],
                "fetch_errors": [],
                "unknown": [],
            }

            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                for url in urls:
                    try:
                        resp = await client.post(
                            f"{SEARCH_CONSOLE_V1}/urlInspection/index:inspect",
                            json={"inspectionUrl": url, "siteUrl": site_url},
                        )
                        resp.raise_for_status()
                        category = _classify_url_result(url, resp.json())
                        categories[category].append(url)
                    except Exception as url_err:
                        logger.exception("gsc_check_indexing_issues: failed for %s", url)
                        categories["unknown"].append(url)

            return json.dumps(categories, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_check_indexing_issues failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_check_indexing_issues failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_get_performance_overview",
        annotations={
            "title": "Get GSC Site Performance Overview",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_get_performance_overview(
        site_url: str,
        token: AccessToken = CurrentAccessToken(),
        days: int = 28,
    ) -> str:
        """Returns aggregate totals and daily trend data for a GSC property.

        Makes two search analytics queries: one for aggregate totals and one
        for day-by-day breakdown.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            days: Lookback window in days. Defaults to 28.

        Returns:
            str: JSON object with "totals" (aggregate metrics) and
                 "daily_trend" (per-day breakdown).
        """
        try:
            today = date.today()
            end_date = (today - timedelta(days=1)).isoformat()
            start_date = (today - timedelta(days=days)).isoformat()
            query_url = (
                f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}/searchAnalytics/query"
            )

            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=60.0
            ) as client:
                # Aggregate totals (no dimensions)
                r_totals = await client.post(
                    query_url,
                    json={
                        "startDate": start_date,
                        "endDate": end_date,
                        "rowLimit": 1,
                        "dataState": "all",
                    },
                )
                r_totals.raise_for_status()

                # Daily trend
                r_daily = await client.post(
                    query_url,
                    json={
                        "startDate": start_date,
                        "endDate": end_date,
                        "dimensions": ["date"],
                        "rowLimit": 500,
                        "dataState": "all",
                    },
                )
                r_daily.raise_for_status()

            totals_rows = r_totals.json().get("rows", [])
            if totals_rows:
                t = totals_rows[0]
                totals = {
                    "clicks": t["clicks"],
                    "impressions": t["impressions"],
                    "ctr": f"{round(t['ctr'] * 100, 2)}%",
                    "position": round(t["position"], 2),
                }
            else:
                totals = {"clicks": 0, "impressions": 0, "ctr": "0.00%", "position": 0.0}

            daily_rows = r_daily.json().get("rows", [])
            daily_trend = [
                {
                    "date": row["keys"][0],
                    "clicks": row["clicks"],
                    "impressions": row["impressions"],
                    "ctr": round(row["ctr"] * 100, 2),
                    "position": round(row["position"], 2),
                }
                for row in daily_rows
            ]

            return json.dumps({"totals": totals, "daily_trend": daily_trend}, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_get_performance_overview failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_get_performance_overview failed")
            return json.dumps({"error": str(e)})
