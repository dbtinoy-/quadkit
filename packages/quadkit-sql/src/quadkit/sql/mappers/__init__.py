"""Entity mapping system for Quadkit DB"""

from __future__ import annotations

from quadkit.sql.mappers.base import DataMapper, MappingError
from quadkit.sql.mappers.domain_mapper import DomainDataMapper

__all__ = [
    "DataMapper",
    "DomainDataMapper",
    "MappingError",
]
