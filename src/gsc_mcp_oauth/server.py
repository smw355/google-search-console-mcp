"""FastMCP server factory — wires auth and all tools together."""

import os

from fastmcp import FastMCP

from gsc_mcp_oauth.auth import create_auth_provider
from gsc_mcp_oauth.tools.properties import register_property_tools
from gsc_mcp_oauth.tools.analytics import register_analytics_tools
from gsc_mcp_oauth.tools.inspection import register_inspection_tools
from gsc_mcp_oauth.tools.sitemaps import register_sitemap_tools


def create_server(base_url: str | None = None) -> FastMCP:
    """Creates and configures the FastMCP server with OAuth auth and all GSC tools.

    Args:
        base_url: The public URL of this server (e.g. the Cloud Run service URL).
            Used in the OAuth protected resource metadata so MCP clients know
            where to discover auth requirements. Reads MCP_BASE_URL env var
            if not provided.
    """
    if base_url is None:
        base_url = os.environ.get("MCP_BASE_URL", "http://localhost:8080")

    auth = create_auth_provider(base_url=base_url)
    mcp = FastMCP(name="google_search_console_mcp", auth=auth)

    register_property_tools(mcp)
    register_analytics_tools(mcp)
    register_inspection_tools(mcp)
    register_sitemap_tools(mcp)

    return mcp
