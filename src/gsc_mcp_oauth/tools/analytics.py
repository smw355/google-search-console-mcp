"""Search analytics tools: query, advanced query, period comparison, page queries."""

import json
import logging
from datetime import date, timedelta

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken

from gsc_mcp_oauth.gsc_clients import WEBMASTERS_V3, auth_headers, encode_site

logger = logging.getLogger(__name__)

_MAX_ROW_LIMIT = 500
_MAX_ADVANCED_ROW_LIMIT = 25000


def _date_range(days: int) -> tuple[str, str]:
    """Returns (start_date, end_date) strings for a lookback window ending yesterday."""
    today = date.today()
    end = today - timedelta(days=1)
    start = today - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def register_analytics_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="gsc_get_search_analytics",
        annotations={
            "title": "Get GSC Search Analytics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_get_search_analytics(
        site_url: str,
        token: AccessToken = CurrentAccessToken(),
        days: int = 28,
        dimensions: list[str] = ["query"],
        row_limit: int = 100,
        search_type: str = "web",
    ) -> str:
        """Queries Google Search Console search analytics data for a site.

        Returns search performance metrics (clicks, impressions, CTR, position)
        broken down by the requested dimensions.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            days: Lookback window in days (1–500). Defaults to 28.
                  Data ends yesterday; starts <days> ago.
            dimensions: Dimensions to group by. Options: query, page, device,
                        country, date. Defaults to ["query"].
            row_limit: Maximum rows to return (1–500). Defaults to 100.
            search_type: Traffic type. Options: web, image, video, news,
                         discover, googleNews. Defaults to "web".

        Returns:
            str: JSON array of rows. Each row has a "keys" list (dimension values)
                 and "clicks", "impressions", "ctr" (as percentage), "position".
        """
        try:
            if row_limit > _MAX_ROW_LIMIT:
                logger.warning(
                    "gsc_get_search_analytics: row_limit %d exceeds max %d, capping.",
                    row_limit, _MAX_ROW_LIMIT,
                )
                row_limit = _MAX_ROW_LIMIT

            start_date, end_date = _date_range(days)
            body = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": dimensions,
                "rowLimit": row_limit,
                "dataState": "all",
                "type": search_type,
            }

            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=60.0
            ) as client:
                resp = await client.post(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}/searchAnalytics/query",
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

            rows = data.get("rows", [])
            for row in rows:
                if "ctr" in row:
                    row["ctr"] = round(row["ctr"] * 100, 2)
            return json.dumps(rows, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_get_search_analytics failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_get_search_analytics failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_get_advanced_search_analytics",
        annotations={
            "title": "Get Advanced GSC Search Analytics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_get_advanced_search_analytics(
        site_url: str,
        start_date: str,
        end_date: str,
        token: AccessToken = CurrentAccessToken(),
        dimensions: list[str] = ["query"],
        search_type: str = "web",
        row_limit: int = 1000,
        start_row: int = 0,
        sort_by: str | None = None,
        sort_direction: str = "descending",
        dimension_filter_groups: list[dict] | None = None,
    ) -> str:
        """Full-featured GSC search analytics query with explicit date ranges, filtering,
        sorting, and pagination.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            dimensions: Dimensions to group by. Options: query, page, device,
                        country, date. Defaults to ["query"].
            search_type: Traffic type. Options: web, image, video, news,
                         discover, googleNews. Defaults to "web".
            row_limit: Maximum rows to return (1–25000). Defaults to 1000.
            start_row: Pagination offset (0-based). Defaults to 0.
            sort_by: Field to sort by. Options: clicks, impressions, ctr, position.
            sort_direction: Sort direction. Options: ascending, descending.
                            Defaults to "descending".
            dimension_filter_groups: Raw filterGroups array per the GSC API spec.
                Example: [{"filters": [{"dimension": "query", "operator": "contains",
                "expression": "python"}]}]

        Returns:
            str: JSON object with "rows" array and "responseAggregationType".
        """
        try:
            if row_limit > _MAX_ADVANCED_ROW_LIMIT:
                logger.warning(
                    "gsc_get_advanced_search_analytics: row_limit %d exceeds max %d, capping.",
                    row_limit, _MAX_ADVANCED_ROW_LIMIT,
                )
                row_limit = _MAX_ADVANCED_ROW_LIMIT

            body: dict = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": dimensions,
                "rowLimit": row_limit,
                "startRow": start_row,
                "dataState": "all",
                "type": search_type,
            }

            if dimension_filter_groups:
                body["dimensionFilterGroups"] = dimension_filter_groups

            if sort_by:
                body["orderBy"] = [{"fieldName": sort_by, "sortOrder": sort_direction}]

            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=60.0
            ) as client:
                resp = await client.post(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}/searchAnalytics/query",
                    json=body,
                )
                resp.raise_for_status()
                return json.dumps(resp.json(), indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_get_advanced_search_analytics failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_get_advanced_search_analytics failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_compare_periods",
        annotations={
            "title": "Compare GSC Search Performance Across Two Periods",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def gsc_compare_periods(
        site_url: str,
        period1_start: str,
        period1_end: str,
        period2_start: str,
        period2_end: str,
        token: AccessToken = CurrentAccessToken(),
        dimensions: list[str] = ["query"],
        row_limit: int = 50,
    ) -> str:
        """Compares search performance metrics between two date ranges.

        Makes two separate search analytics queries and joins results on dimension
        keys, returning absolute and percentage changes in clicks, impressions,
        CTR, and position.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            period1_start: First period start date (YYYY-MM-DD).
            period1_end: First period end date (YYYY-MM-DD).
            period2_start: Second period start date (YYYY-MM-DD).
            period2_end: Second period end date (YYYY-MM-DD).
            dimensions: Dimensions to group by. Defaults to ["query"].
            row_limit: Top N rows to compare per period. Defaults to 50.

        Returns:
            str: JSON array sorted by absolute click change (descending).
                 Each item includes dimension keys and changes for all metrics.
        """
        try:
            def _build_body(start: str, end: str) -> dict:
                return {
                    "startDate": start,
                    "endDate": end,
                    "dimensions": dimensions,
                    "rowLimit": min(row_limit, _MAX_ROW_LIMIT),
                    "dataState": "all",
                }

            url = f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}/searchAnalytics/query"

            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=60.0
            ) as client:
                r1 = await client.post(url, json=_build_body(period1_start, period1_end))
                r1.raise_for_status()
                r2 = await client.post(url, json=_build_body(period2_start, period2_end))
                r2.raise_for_status()

            def _index(rows: list[dict]) -> dict[str, dict]:
                return {"|".join(r["keys"]): r for r in rows}

            p1 = _index(r1.json().get("rows", []))
            p2 = _index(r2.json().get("rows", []))
            all_keys = set(p1) | set(p2)

            comparison = []
            for key in all_keys:
                row1 = p1.get(key, {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0})
                row2 = p2.get(key, {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0})
                keys = key.split("|")

                def _pct(old: float, new: float) -> float | None:
                    if old == 0:
                        return None
                    return round((new - old) / old * 100, 2)

                comparison.append({
                    "keys": keys,
                    "period1": {
                        "clicks": row1["clicks"],
                        "impressions": row1["impressions"],
                        "ctr": round(row1["ctr"] * 100, 2),
                        "position": round(row1["position"], 2),
                    },
                    "period2": {
                        "clicks": row2["clicks"],
                        "impressions": row2["impressions"],
                        "ctr": round(row2["ctr"] * 100, 2),
                        "position": round(row2["position"], 2),
                    },
                    "change": {
                        "clicks": row2["clicks"] - row1["clicks"],
                        "clicks_pct": _pct(row1["clicks"], row2["clicks"]),
                        "impressions": row2["impressions"] - row1["impressions"],
                        "impressions_pct": _pct(row1["impressions"], row2["impressions"]),
                        "ctr": round((row2["ctr"] - row1["ctr"]) * 100, 2),
                        "position": round(row2["position"] - row1["position"], 2),
                    },
                })

            comparison.sort(key=lambda x: x["change"]["clicks"], reverse=True)
            return json.dumps(comparison, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_compare_periods failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_compare_periods failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_get_page_queries",
        annotations={
            "title": "Get Queries Driving Traffic to a Specific Page",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_get_page_queries(
        site_url: str,
        page_url: str,
        token: AccessToken = CurrentAccessToken(),
        days: int = 28,
        row_limit: int = 50,
    ) -> str:
        """Returns the top search queries driving impressions and clicks to a specific page.

        Filters the search analytics data to a single page URL and returns
        the query breakdown with a totals row appended.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            page_url: The specific page URL to analyze
                      (e.g. "https://example.com/blog/my-post/").
            days: Lookback window in days. Defaults to 28.
            row_limit: Maximum queries to return (1–500). Defaults to 50.

        Returns:
            str: JSON array of query rows plus a "__totals__" summary row.
        """
        try:
            if row_limit > _MAX_ROW_LIMIT:
                row_limit = _MAX_ROW_LIMIT

            start_date, end_date = _date_range(days)
            body = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["query"],
                "rowLimit": row_limit,
                "dataState": "all",
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "page",
                        "operator": "equals",
                        "expression": page_url,
                    }]
                }],
            }

            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=60.0
            ) as client:
                resp = await client.post(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}/searchAnalytics/query",
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

            rows = data.get("rows", [])
            for row in rows:
                if "ctr" in row:
                    row["ctr"] = round(row["ctr"] * 100, 2)

            if rows:
                totals = {
                    "keys": ["__totals__"],
                    "clicks": sum(r["clicks"] for r in rows),
                    "impressions": sum(r["impressions"] for r in rows),
                    "ctr": round(
                        sum(r["clicks"] for r in rows) /
                        max(sum(r["impressions"] for r in rows), 1) * 100, 2
                    ),
                    "position": round(
                        sum(r.get("position", 0) for r in rows) / len(rows), 2
                    ),
                }
                rows.append(totals)

            return json.dumps(rows, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_get_page_queries failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_get_page_queries failed")
            return json.dumps({"error": str(e)})
