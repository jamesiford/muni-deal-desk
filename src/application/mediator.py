"""A minimal type-dispatched mediator.

Hosts send messages; handlers are resolved by message type. This keeps the MCP server
and the workflow orchestrator decoupled from handler construction, and lets both reach
the same handler instance so a calculation or policy is implemented exactly once.

Deliberately hand-rolled rather than taken from a library: it is short enough to read
on screen during a walkthrough, and it avoids a dependency whose behaviour would have
to be explained rather than shown.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

TMessage = TypeVar("TMessage")
TResult = TypeVar("TResult")


@runtime_checkable
class Handler(Protocol[TMessage, TResult]):
    """Handles exactly one message type."""

    async def handle(self, message: TMessage) -> TResult:
        """Execute the use case for this message."""
        ...


class HandlerNotRegisteredError(LookupError):
    """Raised when a message is sent with no registered handler."""

    def __init__(self, message_type: type) -> None:
        super().__init__(
            f"No handler registered for {message_type.__name__}. "
            "Register one in the host composition root."
        )


class Mediator:
    """Routes messages to their registered handler.

    Registration happens once in a host composition root, which is the only place that
    knows about concrete infrastructure adapters.
    """

    def __init__(self) -> None:
        self._handlers: dict[type, Any] = {}

    def register(self, message_type: type[TMessage], handler: Handler[TMessage, Any]) -> None:
        """Bind a handler to a message type, replacing any existing binding."""
        self._handlers[message_type] = handler

    async def send(self, message: Any) -> Any:
        """Dispatch a message to its handler and return the result."""
        handler = self._handlers.get(type(message))
        if handler is None:
            raise HandlerNotRegisteredError(type(message))
        return await handler.handle(message)

    @property
    def registered_types(self) -> tuple[type, ...]:
        """Message types with a bound handler. Used by host startup diagnostics."""
        return tuple(self._handlers)
