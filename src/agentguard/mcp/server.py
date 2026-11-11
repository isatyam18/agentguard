"""Official MCP Server for AgentGuard.

Exposes guarded tools to autonomous AI buyer agents through the Model Context Protocol.
"""

from typing import Any, Dict, Optional

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    # Fallback compatibility with earlier mcp revisions
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

from agentguard.mcp.gateway import AgentGuardMCPGateway


def create_mcp_server(gateway: Optional[AgentGuardMCPGateway] = None) -> MCPServer:
    """Build and register guarded payment tools on the official MCP Server."""
    active_gateway = gateway or AgentGuardMCPGateway()

    server = MCPServer(
        name="agentguard-gateway",
        instructions=(
            "AgentGuard Guarded Payment Gateway. Autonomous buyer agents can request "
            "purchases through this interface. Every purchase request is strictly gated by "
            "deterministic spending limits and multi-tiered invoice security checks before "
            "any PayPal authorization is held. Agents have no direct access to credentials, "
            "cannot execute arbitrary payments, and cannot approve or capture escrowed funds."
        ),
    )

    @server.tool(
        name="request_purchase",
        description=(
            "Request a purchase on behalf of the buyer. The request is evaluated against "
            "spending caps, merchant allowlists, velocity budgets, and invoice security rules. "
            "If approved, funds are held in PayPal escrow with intent: AUTHORIZE. If high risk, "
            "the request is placed on hold for human review. If policies are breached, it is blocked."
        ),
    )
    async def request_purchase(
        merchant_id: str,
        merchant_name: str,
        amount: str,
        currency: str = "USD",
        description: str = "",
        invoice: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request purchase through the AgentGuard firewall."""
        return await active_gateway.request_purchase(
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            amount=amount,
            currency=currency,
            description=description,
            invoice=invoice,
            idempotency_key=idempotency_key,
        )

    @server.tool(
        name="get_transaction_status",
        description=(
            "Retrieve the current status, decision, and audit events for a transaction "
            "using its internal UUID or external reference."
        ),
    )
    async def get_transaction_status(transaction_id: str) -> Dict[str, Any]:
        """Check status of a prior transaction."""
        return await active_gateway.get_transaction_status(transaction_id=transaction_id)

    @server.tool(
        name="list_pending_approvals",
        description=(
            "List transactions held in the Human-in-the-Loop review queue. "
            "Requires administrative credentials; buyer agents cannot view or modify the queue."
        ),
    )
    async def list_pending_approvals(admin_token: Optional[str] = None) -> Dict[str, Any]:
        """Administrative inspection of pending approval tasks."""
        return await active_gateway.list_pending_approvals(admin_token=admin_token)

    return server


def run_stdio() -> None:
    """Run MCP server over standard I/O for direct agent subprocess integration."""
    server = create_mcp_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    run_stdio()
