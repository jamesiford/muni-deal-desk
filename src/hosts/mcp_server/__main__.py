"""Run the MCP server over streamable HTTP."""

from __future__ import annotations

from src.hosts.mcp_server.composition import create_runtime_server


def main() -> None:
    """Start the production MCP transport."""
    create_runtime_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()
