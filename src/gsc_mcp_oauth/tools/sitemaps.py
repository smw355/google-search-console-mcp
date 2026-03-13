"""Sitemap management tools: list, get details, submit, delete."""

import json
import logging

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken

from gsc_mcp_oauth.gsc_clients import (
    WEBMASTERS_V3,
    auth_headers,
    encode_feedpath,
    encode_site,
)

logger = logging.getLogger(__name__)


def register_sitemap_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="gsc_list_sitemaps",
        annotations={
            "title": "List GSC Sitemaps",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_list_sitemaps(
        site_url: str,
        token: AccessToken = CurrentAccessToken(),
        sitemap_index: str | None = None,
    ) -> str:
        """Lists all sitemaps submitted for a GSC property.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            sitemap_index: Optional sitemap index URL to filter results.
                           Only returns sitemaps under this index.

        Returns:
            str: JSON array of sitemap objects with path, lastSubmitted,
                 isPending, isSitemapsIndex, lastDownloaded, warnings,
                 errors, and contents breakdown.
        """
        try:
            params = {}
            if sitemap_index:
                # Pass raw value — httpx encodes query params automatically.
                # encode_feedpath() is for path segments only; using it here
                # would cause double-encoding.
                params["sitemapIndex"] = sitemap_index

            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.get(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}/sitemaps",
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
                return json.dumps(data.get("sitemap", []), indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_list_sitemaps failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_list_sitemaps failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_get_sitemap_details",
        annotations={
            "title": "Get GSC Sitemap Details",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_get_sitemap_details(
        site_url: str,
        sitemap_url: str,
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Returns full details for a specific sitemap in GSC.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            sitemap_url: The full sitemap URL
                         (e.g. "https://example.com/sitemap.xml").

        Returns:
            str: JSON object with complete sitemap resource including
                 path, lastSubmitted, lastDownloaded, warnings, errors,
                 and full contents breakdown (type, submitted, indexed).
        """
        try:
            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.get(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}"
                    f"/sitemaps/{encode_feedpath(sitemap_url)}"
                )
                resp.raise_for_status()
                return json.dumps(resp.json(), indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_get_sitemap_details failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_get_sitemap_details failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_submit_sitemap",
        annotations={
            "title": "Submit Sitemap to GSC",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_submit_sitemap(
        site_url: str,
        sitemap_url: str,
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Submits a sitemap to Google Search Console for a verified property.

        The sitemap URL must be publicly accessible. GSC will fetch and process
        the sitemap asynchronously after submission.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            sitemap_url: The full sitemap URL to submit
                         (e.g. "https://example.com/sitemap.xml").

        Returns:
            str: JSON success message or structured error.
        """
        try:
            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.put(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}"
                    f"/sitemaps/{encode_feedpath(sitemap_url)}"
                )
                if resp.status_code == 204:
                    return json.dumps({"success": True, "submitted": sitemap_url})
                if resp.status_code == 400:
                    detail = resp.json() if resp.content else {}
                    return json.dumps({
                        "success": False,
                        "error": "Bad request — check that the sitemap URL is valid and publicly accessible.",
                        "detail": detail,
                    })
                if resp.status_code == 403:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = resp.text
                    return json.dumps({
                        "success": False,
                        "error": "Permission denied.",
                        "detail": detail,
                    })
                if resp.status_code == 404:
                    return json.dumps({
                        "success": False,
                        "error": "GSC property not found. Verify the site_url is registered and verified.",
                    })
                resp.raise_for_status()
                return json.dumps({"success": True, "submitted": sitemap_url})
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_submit_sitemap failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_submit_sitemap failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_delete_sitemap",
        annotations={
            "title": "Delete Sitemap from GSC",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_delete_sitemap(
        site_url: str,
        sitemap_url: str,
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Removes a sitemap from Google Search Console.

        WARNING: This removes the sitemap from GSC tracking. The sitemap file
        itself is not deleted — it remains on your server. Re-submitting is
        possible at any time.

        Args:
            site_url: GSC property URL (e.g. "https://example.com/").
            sitemap_url: The full sitemap URL to delete
                         (e.g. "https://example.com/sitemap.xml").

        Returns:
            str: JSON confirmation or structured error.
        """
        try:
            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.delete(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}"
                    f"/sitemaps/{encode_feedpath(sitemap_url)}"
                )
                if resp.status_code == 204:
                    return json.dumps({"success": True, "deleted": sitemap_url})
                if resp.status_code == 404:
                    return json.dumps({
                        "success": False,
                        "error": "Sitemap not found in GSC.",
                        "sitemapUrl": sitemap_url,
                    })
                if resp.status_code == 403:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = resp.text
                    return json.dumps({
                        "success": False,
                        "error": "Permission denied.",
                        "detail": detail,
                    })
                resp.raise_for_status()
                return json.dumps({"success": True, "deleted": sitemap_url})
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_delete_sitemap failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_delete_sitemap failed")
            return json.dumps({"error": str(e)})
