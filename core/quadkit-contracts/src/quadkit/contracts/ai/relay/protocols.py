"""Relay conversion service protocols.

Gateway and LLM packages consume these protocols from the container and
never import concrete relay implementation modules.  The concrete engine
in ``quadkit-ai-relay`` implements them.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeAlias, runtime_checkable

from quadkit.contracts.ai.exceptions import RelayError
from quadkit.contracts.ai.relay.context import RelayConversionContext
from quadkit.contracts.ai.relay.types import (
    ConversionQuality,
    RelayConvertResult,
    RelayFormat,
    RelayRequestPayload,
    RelayResponsePayload,
)
from quadkit.contracts.core.result import Result

__all__ = [
    "RelayConverterProtocol",
    "RelayMapperProtocol",
    "RelayRegistryProtocol",
    "RelayStreamOptions",
    "RelayStreamSessionProtocol",
]


RelayStreamOptions: TypeAlias = dict[str, Any]
"""Stream options (include_usage, per-target knobs) for a stream session."""


@runtime_checkable
class RelayConverterProtocol(Protocol):
    """Explicit source/target protocol conversion and stream ownership.

    The engine is synchronous, side-effect free, and performs no HTTP,
    channel selection, billing, or model selection.  Callers supply the
    already-selected upstream model and any host callbacks via context.
    """

    def convert_request(
        self,
        payload: RelayRequestPayload,
        source: RelayFormat,
        target: RelayFormat,
        *,
        context: RelayConversionContext | None = None,
        registry: RelayRegistryProtocol | None = None,
    ) -> Result[RelayConvertResult[RelayRequestPayload], RelayError]:
        """Convert a request payload from *source* to *target*."""
        ...

    def convert_response(
        self,
        payload: RelayResponsePayload,
        source: RelayFormat,
        target: RelayFormat,
        *,
        context: RelayConversionContext | None = None,
        registry: RelayRegistryProtocol | None = None,
    ) -> Result[RelayConvertResult[RelayResponsePayload], RelayError]:
        """Convert a non-stream response payload from *source* to *target*."""
        ...

    def new_stream_session(
        self,
        source: RelayFormat,
        target: RelayFormat,
        *,
        options: RelayStreamOptions | None = None,
        context: RelayConversionContext | None = None,
        registry: RelayRegistryProtocol | None = None,
    ) -> Result[RelayStreamSessionProtocol, RelayError]:
        """Create a stateful stream session for one upstream stream."""
        ...

    def convert_stream_chunk(
        self,
        session: RelayStreamSessionProtocol,
        event: Any,
    ) -> tuple[Any, ...]:
        """Convert one source stream event through *session*.

        Args:
            session: A session previously returned by ``new_stream_session``.
            event: One source wire event.

        Returns:
            Zero, one, or many target wire events.

        Raises:
            RelayError: Wrong source format, already finalized, or
                malformed event.
        """
        ...

    def finalize(
        self,
        session: RelayStreamSessionProtocol,
    ) -> tuple[Any, ...]:
        """Close the stream deterministically and return terminal events.

        Args:
            session: A session previously returned by ``new_stream_session``.

        Returns:
            Target terminal events; empty when already finalized.
        """
        ...


@runtime_checkable
class RelayStreamSessionProtocol(Protocol):
    """One mutable upstream stream, owned by the caller.

    The session accepts exactly one source-format event at a time,
    emits zero, one, or many target events, and finalizes idempotently.
    """

    def accept(self, event: Any) -> tuple[Any, ...]:
        """Accept one source wire event and return emitted target events.

        Args:
            event: One source wire event (DTO or raw dict per mapper).

        Returns:
            Zero, one, or many target wire events.

        Raises:
            RelayError: Wrong source format, already finalized, or
                malformed event.
        """
        ...

    def finalize(self) -> tuple[Any, ...]:
        """Close the stream deterministically and return terminal events.

        Repeated calls return an empty tuple without mutation.
        """
        ...

    def snapshot(self) -> Any:
        """Return a read-only snapshot of the session state."""
        ...


@runtime_checkable
class RelayMapperProtocol(Protocol):
    """One wire format's bidirectional mapping to the canonical IR.

    A mapper may reject a feature with a ``RelayLoss`` plus a warning,
    but must raise ``RelayError`` for malformed or impossible payloads.
    """

    def request_to_ir(self, payload: Any) -> Any:
        """Convert a source request DTO into canonical ``RelayRequest``."""
        ...

    def ir_to_request(self, request: Any) -> Any:
        """Convert a canonical ``RelayRequest`` into the target request DTO."""
        ...

    def response_to_ir(self, payload: Any) -> Any:
        """Convert a source response DTO into canonical ``RelayResponse``."""
        ...

    def ir_to_response(self, response: Any) -> Any:
        """Convert a canonical ``RelayResponse`` into the target response DTO."""
        ...

    def stream_to_delta(self, event: Any) -> tuple[Any, ...]:
        """Convert one source stream event into canonical ``StreamDelta``s."""
        ...

    def delta_to_stream(self, delta: Any) -> tuple[Any, ...]:
        """Convert one canonical ``StreamDelta`` into target stream events."""
        ...


@runtime_checkable
class RelayRegistryProtocol(Protocol):
    """Route lookup and caller-owned mapper registration."""

    def mapper(
        self,
        source: RelayFormat,
        target: RelayFormat,
    ) -> RelayMapperProtocol | None:
        """Return the mapper for a directed pair, or ``None``.

        Args:
            source: Source wire format.
            target: Target wire format.

        Returns:
            The registered mapper, or ``None`` when the route is unknown.
        """
        ...

    def converter_routes(self) -> tuple[tuple[RelayFormat, RelayFormat], ...]:
        """Return every supported directed route pair.

        Returns:
            Sorted route pairs; same-format no-op pairs are excluded.
        """
        ...

    def mapper_ids(self) -> tuple[str, ...]:
        """Return the registered mapper wire-format identifiers.

        Returns:
            Sorted mapper ids, one per registered mapper.
        """
        ...

    def converter_version(self) -> str:
        """Return the converter engine version string.

        Returns:
            A version string suitable for diagnostics display.
        """
        ...

    def route_quality(
        self,
        source: RelayFormat,
        target: RelayFormat,
    ) -> ConversionQuality:
        """Return the semantic-closeness quality for a directed pair.

        Same-format pairs are always ``GOOD``; unknown routes fall back
        to ``DISCOURAGED`` rather than raising.

        Args:
            source: Source wire format.
            target: Target wire format.

        Returns:
            The stable quality value for the pair.
        """
        ...
