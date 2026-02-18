# havona-mcp

MCP server for the [Havona](https://github.com/havona-labs) trade finance API. Connect any MCP-compatible AI assistant to live trade contracts, blockchain status, and document extraction.

---

## Tools

| Tool | Description |
|------|-------------|
| `list_trades` | List recent trade contracts |
| `get_trade` | Fetch a trade by ID |
| `create_trade` | Create a new trade contract |
| `update_trade_status` | Update status (DRAFT → ACTIVE → COMPLETED) |
| `blockchain_status` | Check chain connection + contract address |
| `get_trade_blockchain_record` | Get on-chain confirmation for a trade |
| `list_agents` | List registered ERC-8004 AI agents |
| `get_agent_reputation` | Get agent reputation score |
| `list_supported_document_types` | List extractable ETR document types |
| `extract_trade_document` | Extract fields from a PDF (AI, no persistence) |
| `graphql_query` | Raw GraphQL passthrough |

---

## Install

```bash
pip install havona-mcp
```

Or from source:

```bash
git clone https://github.com/havona-labs/havona-mcp
cd havona-mcp
pip install -e .
```

---

## Configuration

Copy `.env.example` to `.env`:

```
HAVONA_API_URL=https://api.yourdomain.com
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_AUDIENCE=https://api.yourdomain.com
AUTH0_CLIENT_ID=your_client_id
HAVONA_EMAIL=trader@yourdomain.com
HAVONA_PASSWORD=your_password
```

---

## Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "havona": {
      "command": "python",
      "args": ["-m", "havona_mcp"],
      "env": {
        "HAVONA_API_URL": "https://api.yourdomain.com",
        "AUTH0_DOMAIN": "your-tenant.us.auth0.com",
        "AUTH0_AUDIENCE": "https://api.yourdomain.com",
        "AUTH0_CLIENT_ID": "your_client_id",
        "HAVONA_EMAIL": "trader@yourdomain.com",
        "HAVONA_PASSWORD": "your_password"
      }
    }
  }
}
```

Restart Claude Desktop. You can now ask:

> "Show me my recent trades"
> "What's the blockchain status?"
> "Create a draft trade for 50,000 barrels of crude oil"
> "Extract the fields from this commercial invoice PDF"

## Cursor / other MCP clients

```bash
python -m havona_mcp          # stdio (default)
python -m havona_mcp --sse    # SSE transport for web clients
```

---

## Architecture

```
Claude Desktop / Cursor
        │  MCP protocol (stdio or SSE)
        ▼
  havona-mcp  (this repo)
        │  Python function calls
        ▼
  havona-sdk
        │  HTTPS + Bearer token
        ▼
  Havona API  →  DGraph + Confidential EVM
```

---

## License

MIT — see [LICENSE](LICENSE).
