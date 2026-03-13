# Google Search Console MCP Server
Connect your AI agents to Google Search Console data. Query search analytics, inspect URL indexing status, manage sitemaps, and monitor site performance — all through your Google account using OAuth.

## Authentication
Sign in with your Google account. The server requests full access to Google Search Console (`webmasters`), which covers both read and write operations. Only properties your Google account can already access in the Search Console interface are available here.

## Tools

### Property Management
**`gsc_list_properties`**
Lists every Search Console property accessible to the authenticated user, including permission level. Start here to discover the exact site URLs needed for all other tools.

**`gsc_get_site_details`**
Returns details for a specific property — site URL, permission level, and verification state.

**`gsc_add_site`**
Adds a new site to your Search Console account. The site will require ownership verification before full data becomes available.

**`gsc_delete_site`**
Removes a site from your Search Console account. This action is irreversible.

---

### Search Analytics
**`gsc_get_search_analytics`**
Query search performance data for a property over a rolling date window. Break down clicks, impressions, CTR, and average position by query, page, device, country, or date. The go-to tool for understanding what searches drive traffic to a site.

**`gsc_get_advanced_search_analytics`**
Full-featured analytics query with explicit date ranges, dimension filtering, sorting, and pagination. Supports up to 25,000 rows and the complete GSC filter API — useful for large exports or precise query segmentation.

**`gsc_compare_periods`**
Compares search performance between two date ranges. Returns absolute and percentage changes in clicks, impressions, CTR, and position for each dimension key, sorted by click change. Useful for before/after analysis around launches, algorithm updates, or campaigns.

**`gsc_get_page_queries`**
Returns the top search queries driving impressions and clicks to a specific page URL, with a totals row appended. Useful for per-page SEO analysis and content optimization.

---

### URL Inspection
**`gsc_inspect_url`**
Inspects a single URL using the Search Console URL Inspection API. Returns full indexing details: verdict (PASS/FAIL), crawl state, robots.txt status, canonical URLs (declared vs. Google's), page fetch state, last crawl time, and detected rich result types.

**`gsc_batch_inspect_urls`**
Inspects up to 10 URLs and returns individual results alongside a summary count of indexed, not-indexed, and errored URLs.

**`gsc_check_indexing_issues`**
Inspects up to 10 URLs and categorizes each one by issue type: `indexed`, `not_indexed`, `robots_blocked`, `canonical_mismatch`, `fetch_errors`, or `unknown`. Useful for quickly triaging a list of pages.

**`gsc_get_performance_overview`**
Returns aggregate totals (clicks, impressions, CTR, position) and a full daily trend breakdown for a property over a rolling date window. Good for a quick health check on any site.

---

### Sitemaps
**`gsc_list_sitemaps`**
Lists all sitemaps submitted for a property, including submission date, last download date, warning/error counts, and URL type breakdown (web, image, video). Optionally filter to sitemaps under a specific sitemap index.

**`gsc_get_sitemap_details`**
Returns full details for a specific sitemap, including the complete content breakdown of submitted vs. indexed URLs by type.

**`gsc_submit_sitemap`**
Submits a sitemap URL to Search Console. Google will fetch and process it asynchronously.

**`gsc_delete_sitemap`**
Removes a sitemap from Search Console tracking. The sitemap file on your server is not affected and can be resubmitted at any time.

---

## Example Prompts
- *"What Search Console properties do I have access to?"*
- *"Show me the top 50 queries by clicks for example.com over the last 28 days."*
- *"Compare search performance for this month vs. last month — what queries gained the most clicks?"*
- *"What queries are driving traffic to my homepage?"*
- *"Is https://example.com/blog/my-post/ indexed by Google? If not, why?"*
- *"Check these 10 URLs and tell me which ones have indexing issues and what kind."*
- *"Show me the daily click trend for example.com over the past 30 days."*
- *"List all submitted sitemaps for my site and flag any with errors."*
- *"Submit https://example.com/sitemap.xml to Search Console."*
