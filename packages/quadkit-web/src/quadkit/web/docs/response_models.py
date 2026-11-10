"""Documentation models for the native CRUD template's concrete envelopes.

These declarations do not validate, transform or redact handler results. They
are used through response_schema_model, not runtime response_model mapping.
The generic CRUD collection is items/limit, deliberately not Page pagination.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

Item = TypeVar("Item")


class CrudCollectionResponse(BaseModel, Generic[Item]):
    """The native CRUD collection envelope."""

    items: list[Item]
    limit: int


class CrudDeleteResponse(BaseModel):
    """The native CRUD delete acknowledgement."""

    message: str
