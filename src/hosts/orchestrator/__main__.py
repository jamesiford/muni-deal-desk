"""Run the Deal Desk through the Foundry Invocations protocol."""

from __future__ import annotations

from src.hosts.orchestrator.composition import create_runtime_server


def main() -> None:
    """Start the hosted agent server."""
    server, port = create_runtime_server()
    server.run(port=port)


if __name__ == "__main__":
    main()
