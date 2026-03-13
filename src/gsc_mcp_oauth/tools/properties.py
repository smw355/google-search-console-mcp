"""Property management tools: list, get, add, delete GSC sites."""

import json
import logging

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.dependencies import CurrentAccessToken

from gsc_mcp_oauth.gsc_clients import WEBMASTERS_V3, auth_headers, encode_site

logger = logging.getLogger(__name__)


def register_property_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="gsc_list_properties",
        annotations={
            "title": "List GSC Properties",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_list_properties(token: AccessToken = CurrentAccessToken()) -> str:
        """Lists all verified Google Search Console properties the authenticated user can access.

        This is typically the first tool called to discover available site URLs
        before calling analytics, inspection, or sitemap tools.

        Returns:
            str: JSON array of site objects, each with siteUrl and permissionLevel.
        """
        try:
            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.get(f"{WEBMASTERS_V3}/sites")
                resp.raise_for_status()
                data = resp.json()
                return json.dumps(data.get("siteEntry", []), indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_list_properties failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_list_properties failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_get_site_details",
        annotations={
            "title": "Get GSC Site Details",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_get_site_details(
        site_url: str,
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Returns details about a specific Google Search Console property.

        Args:
            site_url: The full site URL as registered in GSC
                (e.g. "https://example.com/" or "sc-domain:example.com").

        Returns:
            str: JSON object with siteUrl, permissionLevel, and verificationState.
        """
        try:
            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.get(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}"
                )
                resp.raise_for_status()
                return json.dumps(resp.json(), indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_get_site_details failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_get_site_details failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_add_site",
        annotations={
            "title": "Add GSC Site",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_add_site(
        site_url: str,
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Adds a site to the authenticated user's Google Search Console account.

        The site must be a valid URL. After adding, the user will need to verify
        ownership before full data becomes available.

        Args:
            site_url: The full site URL to add
                (e.g. "https://example.com/" or "sc-domain:example.com").

        Returns:
            str: JSON success message or structured error.
        """
        try:
            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.put(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}"
                )
                if resp.status_code == 204:
                    return json.dumps({"success": True, "siteUrl": site_url})
                if resp.status_code == 409:
                    return json.dumps({"success": False, "error": "Site already exists in GSC.", "siteUrl": site_url})
                if resp.status_code == 403:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = resp.text
                    return json.dumps({"success": False, "error": "Permission denied.", "detail": detail, "siteUrl": site_url})
                if resp.status_code == 400:
                    detail = resp.json() if resp.content else {}
                    return json.dumps({"success": False, "error": "Bad request — invalid site URL format.", "detail": detail, "siteUrl": site_url})
                resp.raise_for_status()
                return json.dumps({"success": True, "siteUrl": site_url})
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_add_site failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_add_site failed")
            return json.dumps({"error": str(e)})

    @mcp.tool(
        name="gsc_delete_site",
        annotations={
            "title": "Delete GSC Site",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def gsc_delete_site(
        site_url: str,
        token: AccessToken = CurrentAccessToken(),
    ) -> str:
        """Removes a site from the authenticated user's Google Search Console account.

        WARNING: This action is irreversible. The site and its associated data
        will be removed from the user's GSC account. Ownership verification
        will need to be repeated if re-added.

        Args:
            site_url: The full site URL to delete
                (e.g. "https://example.com/" or "sc-domain:example.com").

        Returns:
            str: JSON success confirmation or structured error.
        """
        try:
            async with httpx.AsyncClient(
                headers=auth_headers(token.token), timeout=30.0
            ) as client:
                resp = await client.delete(
                    f"{WEBMASTERS_V3}/sites/{encode_site(site_url)}"
                )
                if resp.status_code == 204:
                    return json.dumps({"success": True, "deleted": site_url})
                if resp.status_code == 404:
                    return json.dumps({"success": False, "error": "Site not found in GSC.", "siteUrl": site_url})
                if resp.status_code == 403:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = resp.text
                    return json.dumps({"success": False, "error": "Permission denied.", "detail": detail, "siteUrl": site_url})
                resp.raise_for_status()
                return json.dumps({"success": True, "deleted": site_url})
        except httpx.HTTPStatusError as e:
            logger.exception("gsc_delete_site failed: HTTP %s — %s", e.response.status_code, e.response.text)
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            return json.dumps({"error": f"Google API error {e.response.status_code}", "detail": detail})
        except Exception as e:
            logger.exception("gsc_delete_site failed")
            return json.dumps({"error": str(e)})
