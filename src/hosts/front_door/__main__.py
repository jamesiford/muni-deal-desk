"""Run the local banker-facing application."""

from __future__ import annotations

import uvicorn

from src.hosts.front_door.composition import create_runtime_app


def main() -> None:
    """Start FastAPI and serve the built Vite application when present."""
    app, settings = create_runtime_app()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
