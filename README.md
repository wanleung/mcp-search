# Google Search MCP Server

A Python MCP server that provides Google Search and page fetching tools to Ollama-based AI agents. Results are cached in Elasticsearch.

## Tools

| Tool | Description |
|------|-------------|
| `google_search` | Search the web, returns title, URL, snippet per result (cached 24h). Falls back to DuckDuckGo if Google scraping is unavailable. |
| `google_fetch_page` | Fetch full text content of a URL (cached 7 days) |

## Quick Start

```bash
# Copy env config
cp .env.example .env

# Start all services (Elasticsearch + MCP server)
docker compose up -d --build
```

Wait ~30–60 seconds for Elasticsearch to become healthy, then verify:

```bash
# Check service status
docker compose ps

# Verify Elasticsearch health
curl -s http://localhost:9200/_cluster/health | python3 -m json.tool
```

## Connecting to Ollama Agent

The MCP server uses **streamable-http** transport and requires a two-step connection:

### Step 1: Initialize a session

```bash
curl -si -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"my-agent","version":"1.0"}}}'
```

Note the `mcp-session-id` header returned in the response.

### Step 2: Use the session ID for subsequent requests

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

### Add to your agent's MCP config

```json
{
  "mcpServers": {
    "google_search": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

> **Note:** The MCP client library handles the session initialization handshake automatically when connecting via URL. Manual session management is only required when using raw HTTP clients.

## Tool Usage Examples

### `google_search`

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "google_search",
      "arguments": {"query": "Python programming language", "num_results": 3}
    }
  }'
```

### `google_fetch_page`

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <SESSION_ID>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "google_fetch_page",
      "arguments": {"url": "https://www.python.org"}
    }
  }'
```

## Running Tests

```bash
pip install -r requirements.txt
playwright install chromium
pytest -v
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ES_URL` | `http://elasticsearch:9200` | Elasticsearch URL |
| `SERVER_HOST` | `0.0.0.0` | Server bind host |
| `SERVER_PORT` | `8000` | Server port |

## Architecture

```
┌─────────────────┐     MCP (streamable-http)     ┌─────────────────┐
│   Ollama Agent  │ ──────────────────────────────▶│   MCP Server    │
│                 │     http://localhost:8000/mcp  │  (FastMCP)      │
└─────────────────┘                                └────────┬────────┘
                                                            │  cache get/set
                                                   ┌────────▼────────┐
                                                   │ Elasticsearch   │
                                                   │ (port 9200)     │
                                                   └─────────────────┘
```

- **MCP Server** handles tool calls and orchestrates caching
- **Elasticsearch** stores cached search results (24h TTL) and fetched pages (7-day TTL)
- **Google Scraping** is the primary search backend; **DuckDuckGo** is the fallback

## Troubleshooting

### MCP server not reachable

```bash
docker compose logs mcp-server
```

### Elasticsearch unhealthy

```bash
docker compose logs elasticsearch
```

### `Missing session ID` error

The streamable-http transport requires an `mcp-session-id` header on all requests except `initialize`. Initialize first to obtain the session ID (see [Connecting](#connecting-to-ollama-agent)).

### No search results returned

Google scraping may be rate-limited or blocked in certain network environments. The server automatically falls back to DuckDuckGo. If both fail, verify outbound internet access from the container:

```bash
docker compose exec mcp-server curl -s https://www.google.com -o /dev/null -w "%{http_code}"
```
