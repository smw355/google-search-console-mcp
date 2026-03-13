# Google Search Console MCP Server

A stateless, multi-tenant HTTP [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server for Google Search Console, designed to run on Google Cloud Run and connect to AI agent platforms like [Obot](https://obot.ai).

Connect your AI agents to Google Search Console data — query search analytics, inspect URL indexing, manage sitemaps, and monitor site performance — all authenticated through each user's own Google account via OAuth.

---

## How It Works

- Each user signs in with their own Google account through OAuth
- The server validates the user's Bearer token on every request via Google's tokeninfo endpoint
- All Google Search Console API calls are made using that user's token — they can only access properties they already have access to in Search Console
- No credentials are stored on the server; it is fully stateless and multi-tenant

---

## Tools

| # | Tool | Description |
|---|------|-------------|
| 1 | `gsc_list_properties` | List all GSC properties the authenticated user can access |
| 2 | `gsc_get_site_details` | Get details for a specific property |
| 3 | `gsc_add_site` | Add a new site to Search Console |
| 4 | `gsc_delete_site` | Remove a site from Search Console |
| 5 | `gsc_get_search_analytics` | Query clicks, impressions, CTR, and position by query/page/device/country |
| 6 | `gsc_get_advanced_search_analytics` | Full analytics query with date ranges, filters, sorting, and pagination |
| 7 | `gsc_compare_periods` | Compare search performance between two date ranges |
| 8 | `gsc_get_page_queries` | Top queries driving traffic to a specific page |
| 9 | `gsc_inspect_url` | Full URL inspection — indexing status, crawl state, canonicals, rich results |
| 10 | `gsc_batch_inspect_urls` | Inspect up to 10 URLs and return a summary |
| 11 | `gsc_check_indexing_issues` | Categorize up to 10 URLs by indexing issue type |
| 12 | `gsc_get_performance_overview` | Aggregate totals and daily trend for a property |
| 13 | `gsc_list_sitemaps` | List all submitted sitemaps for a property |
| 14 | `gsc_get_sitemap_details` | Full details for a specific sitemap |
| 15 | `gsc_submit_sitemap` | Submit a sitemap URL to Search Console |
| 16 | `gsc_delete_sitemap` | Remove a sitemap from Search Console |

---

## Prerequisites

- [Google Cloud](https://console.cloud.google.com) project with billing enabled
- [Docker](https://www.docker.com) (with `buildx` for Apple Silicon cross-compilation)
- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) — authenticated and configured
- [Obot](https://obot.ai) instance for serving the MCP endpoint to agents

---

## 1. Enable Required Google APIs

In the Google Cloud project that owns your OAuth client, enable the Search Console APIs:

```bash
gcloud services enable webmasters.googleapis.com searchconsole.googleapis.com \
  --project=YOUR_PROJECT_ID
```

---

## 2. Create an OAuth Client in Google Cloud

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Application type: **Web application**
3. Add an authorized redirect URI:
   ```
   https://YOUR_OBOT_HOST/oauth/mcp/callback
   ```
4. Note the **Client ID** and **Client Secret** — you'll need them in Obot

If you already have an OAuth client for another MCP server (e.g. Google Analytics), you can reuse it — just add the `webmasters` scope to your OAuth consent screen:

**APIs & Services → OAuth consent screen → Edit App → Add or remove scopes**

Add: `https://www.googleapis.com/auth/webmasters`

---

## 3. Build and Push the Docker Image

The container must target `linux/amd64` for Cloud Run (important if building on Apple Silicon).

```bash
PROJECT=your-gcp-project-id
REGION=us-central1
REPO=cloud-run-images
IMAGE_NAME=gsc-mcp-oauth
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${IMAGE_NAME}:v1"

# Build for linux/amd64
docker build --platform linux/amd64 -t "${IMAGE_NAME}:v1" .

# Tag and push to Artifact Registry
docker tag "${IMAGE_NAME}:v1" "$IMAGE"
docker push "$IMAGE"
```

> If the Artifact Registry repository doesn't exist yet:
> ```bash
> gcloud artifacts repositories create cloud-run-images \
>   --repository-format=docker \
>   --location=$REGION \
>   --project=$PROJECT
> ```

---

## 4. Deploy to Cloud Run

On the first deploy, use a placeholder `MCP_BASE_URL` — then redeploy once you have the real service URL.

**First deploy (to get the URL):**

```bash
gcloud run deploy gsc-mcp-oauth \
  --image "$IMAGE" \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars MCP_BASE_URL=placeholder \
  --project $PROJECT
```

**Capture the assigned URL from the output, then redeploy with it:**

```bash
SERVICE_URL="https://gsc-mcp-oauth-XXXXXXXXXX.us-central1.run.app"

gcloud run deploy gsc-mcp-oauth \
  --image "$IMAGE" \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars MCP_BASE_URL=$SERVICE_URL \
  --project $PROJECT
```

---

## 5. Verify the Deployment

```bash
SERVICE_URL="https://gsc-mcp-oauth-XXXXXXXXXX.us-central1.run.app"

# Protected resource metadata — should list Google as the authorization server
curl -s "$SERVICE_URL/.well-known/oauth-protected-resource/mcp" | python3 -m json.tool

# No token → should return 401
curl -s -o /dev/null -w "No token → HTTP %{http_code}\n" "$SERVICE_URL/mcp"

# Invalid token → should return 400 (not 500)
curl -s -o /dev/null -w "Bad token → HTTP %{http_code}\n" \
  -H "Authorization: Bearer invalid_token" "$SERVICE_URL/mcp"
```

Expected metadata response:
```json
{
  "resource": "https://your-service-url/mcp",
  "authorization_servers": ["https://accounts.google.com/"],
  "scopes_supported": ["https://www.googleapis.com/auth/webmasters"],
  "bearer_methods_supported": ["header"],
  "resource_name": "Google Search Console MCP Server"
}
```

---

## 6. Connect to Obot

[Obot](https://obot.ai) handles the OAuth flow for your users — they sign in with Google through Obot, and Obot passes their Bearer token to this server on each request.

1. In Obot, go to **MCP Servers → Add MCP Server**
2. Enter the server URL:
   ```
   https://your-service-url/mcp
   ```
3. Go to **Advanced Configuration → Static OAuth** and configure:
   | Field | Value |
   |-------|-------|
   | Authorization Server | `https://accounts.google.com` |
   | Client ID | Your Google OAuth Client ID |
   | Client Secret | Your Google OAuth Client Secret |
   | Scopes | `https://www.googleapis.com/auth/webmasters` |

4. Save — users can now authenticate with their own Google accounts and access their Search Console data through your agents.

---

## Project Structure

```
├── Dockerfile
├── pyproject.toml
└── src/
    └── gsc_mcp_oauth/
        ├── __init__.py
        ├── __main__.py          # Entry point — reads PORT and MCP_BASE_URL
        ├── auth.py              # Token verification + RemoteAuthProvider
        ├── gsc_clients.py       # httpx helpers + URL encoding utilities
        ├── server.py            # FastMCP server factory
        └── tools/
            ├── properties.py    # Site listing, add, delete, details
            ├── analytics.py     # Search analytics queries
            ├── inspection.py    # URL inspection and indexing checks
            └── sitemaps.py      # Sitemap management
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MCP_BASE_URL` | Yes (production) | The public URL of this Cloud Run service — used to generate OAuth metadata endpoints |
| `PORT` | No | HTTP port (default: `8080`, set automatically by Cloud Run) |

---

## Dependencies

- [`fastmcp`](https://github.com/jlowin/fastmcp) >= 3.1.0 — MCP server framework with `RemoteAuthProvider`
- [`httpx`](https://www.python-httpx.org) >= 0.28.1 — async HTTP client for all Google API calls

No `google-api-python-client`, `google-auth`, or gRPC dependencies. Authentication is handled entirely via Bearer token passthrough.

---

## License

MIT
