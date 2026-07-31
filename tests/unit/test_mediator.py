"""Mediator tests.

The mediator is the seam that lets the MCP server and the orchestrator share handlers,
so its dispatch and failure behaviour are worth pinning down.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from src.application.mediator import HandlerNotRegisteredError, Mediator


@dataclass(frozen=True)
class Ping:
    value: str


@dataclass(frozen=True)
class Unhandled:
    value: str


class PingHandler:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def handle(self, message: Ping) -> str:
        self.calls.append(message.value)
        return f"pong:{message.value}"


class TestMediator:
    async def test_dispatches_to_registered_handler(self):
        mediator = Mediator()
        mediator.register(Ping, PingHandler())
        assert await mediator.send(Ping("a")) == "pong:a"

    async def test_raises_for_unregistered_message(self):
        mediator = Mediator()
        with pytest.raises(HandlerNotRegisteredError):
            await mediator.send(Unhandled("x"))

    async def test_error_names_the_message_type(self):
        mediator = Mediator()
        with pytest.raises(HandlerNotRegisteredError, match="Unhandled"):
            await mediator.send(Unhandled("x"))

    async def test_registration_replaces_prior_binding(self):
        mediator = Mediator()
        first, second = PingHandler(), PingHandler()
        mediator.register(Ping, first)
        mediator.register(Ping, second)

        await mediator.send(Ping("a"))

        assert first.calls == []
        assert second.calls == ["a"]

    async def test_reuses_the_same_handler_instance(self):
        # Both hosts resolve one instance, which is what keeps a calculation or policy
        # implemented exactly once.
        mediator = Mediator()
        handler = PingHandler()
        mediator.register(Ping, handler)

        await mediator.send(Ping("a"))
        await mediator.send(Ping("b"))

        assert handler.calls == ["a", "b"]

    async def test_registered_types_reports_bindings(self):
        mediator = Mediator()
        mediator.register(Ping, PingHandler())
        assert Ping in mediator.registered_types
