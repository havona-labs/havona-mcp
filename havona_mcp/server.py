"""
Havona MCP Server

Exposes the Havona trade finance API as MCP tools so any MCP-compatible
AI assistant (Claude Desktop, Cursor, etc.) can query and manage trade
contracts, check blockchain status, and extract trade documents.

Configuration (env vars):
    HAVONA_API_URL          Base URL of your Havona API instance
    AUTH0_DOMAIN            Auth0 tenant domain
    AUTH0_AUDIENCE          Auth0 API audience
    AUTH0_CLIENT_ID         Auth0 SPA / password-grant client ID
    HAVONA_EMAIL            User email (password grant)
    HAVONA_PASSWORD         User password (password grant)

    Or for service accounts (M2M):
    AUTH0_M2M_CLIENT_ID     M2M client ID
    AUTH0_M2M_CLIENT_SECRET M2M client secret

Usage:
    python -m havona_mcp        # stdio transport (Claude Desktop / Cursor)
    python -m havona_mcp --sse  # SSE transport (web clients)
"""

import json
import os
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

from havona_sdk import HavonaClient, HavonaError

mcp = FastMCP(
    name="havona",
    instructions=(
        "Havona trade finance platform. "
        "Use these tools to query trade contracts, check blockchain status, "
        "list AI agents and their reputation scores, and extract structured "
        "data from trade documents (Commercial Invoice, Bill of Lading, etc.)."
    ),
)

# ---------------------------------------------------------------------------
# Client initialisation — lazy, created on first tool call
# ---------------------------------------------------------------------------

_client: Optional[HavonaClient] = None


def _get_client() -> HavonaClient:
    global _client
    if _client is not None:
        return _client

    base_url = os.environ.get("HAVONA_API_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("HAVONA_API_URL environment variable is required")

    # M2M service account takes priority if both sets of creds are present
    m2m_id = os.environ.get("AUTH0_M2M_CLIENT_ID")
    m2m_secret = os.environ.get("AUTH0_M2M_CLIENT_SECRET")
    if m2m_id and m2m_secret:
        _client = HavonaClient.from_m2m(
            base_url=base_url,
            auth0_domain=os.environ["AUTH0_DOMAIN"],
            auth0_audience=os.environ["AUTH0_AUDIENCE"],
            auth0_client_id=m2m_id,
            auth0_client_secret=m2m_secret,
        )
        return _client

    # Fall back to password grant
    _client = HavonaClient.from_credentials(
        base_url=base_url,
        auth0_domain=os.environ["AUTH0_DOMAIN"],
        auth0_audience=os.environ["AUTH0_AUDIENCE"],
        auth0_client_id=os.environ["AUTH0_CLIENT_ID"],
        username=os.environ["HAVONA_EMAIL"],
        password=os.environ["HAVONA_PASSWORD"],
    )
    return _client


def _err(e: Exception) -> str:
    """Serialise an exception to a JSON error string."""
    return json.dumps({"error": str(e), "type": type(e).__name__})


# ---------------------------------------------------------------------------
# Trade tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_trades(limit: int = 20) -> str:
    """
    List trade contracts visible to the authenticated user.

    Returns up to `limit` TradeContract records with id, contractNo,
    status, contractType, and blockchain persistence state.
    """
    try:
        client = _get_client()
        trades = client.trades.list(limit=limit)
        return json.dumps([
            {
                "id": t.id,
                "contractNo": t.contract_no,
                "status": t.status,
                "contractType": t.contract_type,
                "blockchainStatus": t.blockchain_status,
                "txHash": t.tx_hash,
            }
            for t in trades
        ])
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_trade(trade_id: str) -> str:
    """
    Fetch a single trade contract by its ID.

    Args:
        trade_id: The DGraph UUID of the trade contract.

    Returns trade details including blockchain persistence state.
    """
    try:
        client = _get_client()
        t = client.trades.get(trade_id)
        return json.dumps({
            "id": t.id,
            "contractNo": t.contract_no,
            "status": t.status,
            "contractType": t.contract_type,
            "blockchainStatus": t.blockchain_status,
            "txHash": t.tx_hash,
            "blockNumber": t.block_number,
            **t.extra,
        })
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def create_trade(
    contract_no: str,
    status: str = "DRAFT",
    contract_type: Optional[str] = None,
    seller_id: Optional[str] = None,
    buyer_id: Optional[str] = None,
    commodity: Optional[str] = None,
    quantity: Optional[str] = None,
    unit: Optional[str] = None,
    currency: Optional[str] = None,
    total_value: Optional[str] = None,
    origin_country: Optional[str] = None,
    destination_country: Optional[str] = None,
) -> str:
    """
    Create a new trade contract.

    Creates a TradeContract record that is dual-persisted to the database
    and the confidential blockchain. Returns the newly created trade including
    its server-assigned id.

    Args:
        contract_no: Unique contract identifier (e.g. "TC-2026-001").
        status: Initial status — DRAFT (default) or ACTIVE.
        contract_type: e.g. "SPOT", "FORWARD".
        seller_id: Member UUID of the selling party.
        buyer_id: Member UUID of the buying party.
        commodity: Commodity name (e.g. "Crude Oil", "Wheat").
        quantity: Quantity as a string (e.g. "50000").
        unit: Unit of measure (e.g. "BBL", "MT").
        currency: ISO currency code (e.g. "USD").
        total_value: Total contract value as a string.
        origin_country: ISO country code of origin.
        destination_country: ISO country code of destination.
    """
    try:
        client = _get_client()
        kwargs = {"contract_no": contract_no, "status": status}
        if contract_type:
            kwargs["contractType"] = contract_type
        if seller_id:
            kwargs["sellerId"] = seller_id
        if buyer_id:
            kwargs["buyerId"] = buyer_id
        if commodity:
            kwargs["commodity"] = commodity
        if quantity:
            kwargs["quantity"] = quantity
        if unit:
            kwargs["unit"] = unit
        if currency:
            kwargs["currency"] = currency
        if total_value:
            kwargs["totalValue"] = total_value
        if origin_country:
            kwargs["originCountry"] = origin_country
        if destination_country:
            kwargs["destinationCountry"] = destination_country

        trade = client.trades.create(**kwargs)
        return json.dumps({
            "id": trade.id,
            "contractNo": trade.contract_no,
            "status": trade.status,
            "blockchainStatus": trade.blockchain_status,
        })
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def update_trade_status(trade_id: str, status: str) -> str:
    """
    Update the status of an existing trade contract.

    Args:
        trade_id: The DGraph UUID of the trade.
        status: New status (e.g. "ACTIVE", "COMPLETED", "CANCELLED").

    Returns the updated trade.
    """
    try:
        client = _get_client()
        result = client.trades.update(trade_id, status=status)
        return json.dumps(result)
    except HavonaError as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Blockchain tools
# ---------------------------------------------------------------------------


@mcp.tool()
def blockchain_status() -> str:
    """
    Check the blockchain connection status of the Havona platform.

    Returns whether the platform is connected to its confidential EVM chain,
    the chain ID, and the deployed contract address.
    """
    try:
        client = _get_client()
        s = client.blockchain.status()
        return json.dumps({
            "connected": s.connected,
            "chainId": s.chain_id,
            "network": s.network,
            "contractAddress": s.contract_address,
            **s.extra,
        })
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def get_trade_blockchain_record(trade_id: str) -> str:
    """
    Fetch the on-chain persistence record for a trade.

    Returns the blockchain confirmation status, transaction hash, and block
    number. Status is one of: PENDING, CONFIRMED, FAILED.

    Args:
        trade_id: The DGraph UUID of the trade.
    """
    try:
        client = _get_client()
        p = client.blockchain.get_persistence(trade_id)
        return json.dumps({
            "recordId": p.record_id,
            "status": p.status,
            "txHash": p.tx_hash,
            "blockNumber": p.block_number,
            "attemptCount": p.attempt_count,
            "createdAt": p.created_at,
        })
    except HavonaError as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_agents() -> str:
    """
    List all ERC-8004 AI agents registered on the Havona platform.

    Returns each agent's on-chain ID, name, type, wallet address, and status.
    Returns an empty list if the blockchain connection is unavailable.
    """
    try:
        client = _get_client()
        agents = client.agents.list()
        return json.dumps([
            {
                "id": a.id,
                "name": a.name,
                "agentType": a.agent_type,
                "wallet": a.wallet,
                "status": a.status,
                "metadataUri": a.metadata_uri,
            }
            for a in agents
        ])
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def get_agent_reputation(agent_id: int) -> str:
    """
    Get the aggregated reputation score for an AI agent.

    Returns total feedback count, average score (0–5), and a score breakdown
    by category.

    Args:
        agent_id: The integer on-chain agent ID.
    """
    try:
        client = _get_client()
        rep = client.agents.get_reputation(agent_id)
        return json.dumps({
            "agentId": rep.agent_id,
            "totalFeedback": rep.total_feedback,
            "averageScore": rep.average_score,
            "breakdown": rep.breakdown,
        })
    except HavonaError as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Document extraction tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_supported_document_types() -> str:
    """
    List the ETR document types supported for AI extraction.

    Returns document type IDs and names such as COMMERCIAL_INVOICE,
    BILL_OF_LADING, and CERTIFICATE_OF_ORIGIN.
    """
    try:
        client = _get_client()
        types = client.documents.supported_types()
        return json.dumps([
            {"id": t.id, "name": t.name, "description": t.description}
            for t in types
        ])
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def extract_trade_document(file_path: str, document_type: str) -> str:
    """
    Extract structured trade data from an ETR document PDF using AI.

    Sends the PDF to the Havona extraction service (powered by Gemini)
    and returns the extracted fields. **Does not save anything** — call
    create_trade() with the returned fields to persist.

    Args:
        file_path: Absolute path to the PDF file on this machine.
        document_type: One of COMMERCIAL_INVOICE, BILL_OF_LADING,
                       CERTIFICATE_OF_ORIGIN.

    Returns extracted fields, confidence score, and document type.
    """
    try:
        client = _get_client()
        result = client.documents.extract(file_path, document_type)
        return json.dumps({
            "documentType": result.document_type,
            "fields": result.fields,
            "confidence": result.confidence,
            "source": result.source,
        })
    except HavonaError as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Raw passthrough
# ---------------------------------------------------------------------------


@mcp.tool()
def graphql_query(query: str, variables: Optional[str] = None) -> str:
    """
    Execute a raw GraphQL query against the Havona API.

    Use this for advanced queries not covered by the other tools — for example,
    querying nested fields, filtering by multiple criteria, or accessing
    types not exposed elsewhere.

    Args:
        query: GraphQL query string.
        variables: Optional JSON string of query variables.

    Example:
        query = "query { queryTradeContract(first: 5) { id contractNo status } }"
    """
    try:
        client = _get_client()
        vars_dict = json.loads(variables) if variables else None
        data = client.graphql(query, vars_dict)
        return json.dumps(data)
    except HavonaError as e:
        return _err(e)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid variables JSON: {e}"})
