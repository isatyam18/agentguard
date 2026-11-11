"""Top-level entry point for executing the AgentGuard MCP Server."""

from agentguard.mcp.server import create_mcp_server, run_stdio

if __name__ == "__main__":
    run_stdio()
