"""Response factory adapter, building the quadkit response family.

The adapter implements ``ResponseFactoryProtocol`` with
``quadkit.web.transport.responses`` classes (starlette subclasses), so wire
behavior is unchanged while JSON payloads gain ``quadkit.serialization``
serialization (orjson; native datetime/UUID/dataclass handling).
"""

from __future__ import annotations

from quadkit.web.responses.adapter import StarletteResponseAdapter

__all__ = ["StarletteResponseAdapter"]
