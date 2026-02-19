"""
Havona MCP Server

Exposes the Havona trade finance API as MCP tools.

Env vars:
    HAVONA_API_URL          API base URL
    AUTH0_DOMAIN            Auth0 tenant domain
    AUTH0_AUDIENCE          Auth0 API audience
    AUTH0_CLIENT_ID         Client ID (password grant)
    HAVONA_EMAIL / HAVONA_PASSWORD

    For M2M (takes priority if set):
    AUTH0_M2M_CLIENT_ID / AUTH0_M2M_CLIENT_SECRET

Usage:
    python -m havona_mcp        # stdio (Claude Desktop / Cursor)
    python -m havona_mcp --sse  # SSE transport
"""

import json
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from havona_sdk import HavonaClient, HavonaError

mcp = FastMCP(
    name="havona",
    instructions=(
        "Havona trade finance platform. "
        "Query trade contracts, check blockchain status, "
        "inspect AI agent reputation, and extract fields from trade documents."
    ),
)

_client: Optional[HavonaClient] = None


def _get_client() -> HavonaClient:
    global _client
    if _client is not None:
        return _client

    base_url = os.environ.get("HAVONA_API_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("HAVONA_API_URL is required")

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
    else:
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
    return json.dumps({"error": str(e), "type": type(e).__name__})


@mcp.tool()
def list_trades(limit: int = 20) -> str:
    """
    List trade contracts visible to the authenticated user.

    Returns id, contractNo, status, contractType, and blockchain persistence state.
    """
    try:
        trades = _get_client().trades.list(limit=limit)
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
    """
    try:
        t = _get_client().trades.get(trade_id)
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
    Create a new trade contract. Returns the created record including its server-assigned id.

    status: DRAFT (default) or ACTIVE
    contract_type: e.g. SPOT, FORWARD
    seller_id / buyer_id: member UUIDs
    quantity and total_value as strings (e.g. "50000", "4100000.00")
    """
    try:
        kwargs: dict = {"contract_no": contract_no, "status": status}
        for k, v in [
            ("contractType", contract_type),
            ("sellerId", seller_id),
            ("buyerId", buyer_id),
            ("commodity", commodity),
            ("quantity", quantity),
            ("unit", unit),
            ("currency", currency),
            ("totalValue", total_value),
            ("originCountry", origin_country),
            ("destinationCountry", destination_country),
        ]:
            if v is not None:
                kwargs[k] = v

        trade = _get_client().trades.create(**kwargs)
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
    Update the status of a trade contract (e.g. DRAFT → ACTIVE → COMPLETED).
    """
    try:
        result = _get_client().trades.update(trade_id, status=status)
        return json.dumps(result)
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def blockchain_status() -> str:
    """
    Check whether the platform is connected to its confidential EVM chain.

    Returns connected, chainId, network, and the deployed contract address.
    """
    try:
        s = _get_client().blockchain.status()
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
    Get the on-chain persistence record for a trade.

    status is one of PENDING, CONFIRMED, FAILED.
    """
    try:
        p = _get_client().blockchain.get_persistence(trade_id)
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


@mcp.tool()
def list_agents() -> str:
    """
    List ERC-8004 AI agents registered on the platform.

    Returns an empty list if the blockchain connection is unavailable.
    """
    try:
        agents = _get_client().agents.list()
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
    Get the aggregated reputation score for an agent.

    Returns total feedback count, average score (0–5), and a breakdown by category.
    """
    try:
        rep = _get_client().agents.get_reputation(agent_id)
        return json.dumps({
            "agentId": rep.agent_id,
            "totalFeedback": rep.total_feedback,
            "averageScore": rep.average_score,
            "breakdown": rep.breakdown,
        })
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def list_supported_document_types() -> str:
    """
    List ETR document types available for AI extraction.

    Typically includes COMMERCIAL_INVOICE, BILL_OF_LADING, CERTIFICATE_OF_ORIGIN.
    """
    try:
        types = _get_client().documents.supported_types()
        return json.dumps([
            {"id": t.id, "name": t.name, "description": t.description}
            for t in types
        ])
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def extract_trade_document(file_path: str, document_type: str) -> str:
    """
    Extract structured fields from an ETR document PDF using Gemini AI.

    Does not save anything — call create_trade() with the returned fields to persist.

    document_type: COMMERCIAL_INVOICE | BILL_OF_LADING | CERTIFICATE_OF_ORIGIN
    file_path: absolute path to the PDF on this machine
    """
    try:
        result = _get_client().documents.extract(file_path, document_type)
        return json.dumps({
            "documentType": result.document_type,
            "fields": result.fields,
            "confidence": result.confidence,
            "source": result.source,
        })
    except HavonaError as e:
        return _err(e)


@mcp.tool()
def graphql_query(query: str, variables: Optional[str] = None) -> str:
    """
    Run a raw GraphQL query against the Havona API.

    variables: optional JSON string, e.g. '{"id": "abc123"}'

    Example:
        query = "query { queryTradeContract(first: 5) { id contractNo status } }"
    """
    try:
        vars_dict = json.loads(variables) if variables else None
        data = _get_client().graphql(query, vars_dict)
        return json.dumps(data)
    except HavonaError as e:
        return _err(e)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid variables JSON: {e}"})
