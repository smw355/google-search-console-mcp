"""Entry point for the Google Search Console MCP OAuth server."""

import os

from gsc_mcp_oauth.server import create_server


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    base_url = os.environ.get("MCP_BASE_URL", f"http://localhost:{port}")

    mcp = create_server(base_url=base_url)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
