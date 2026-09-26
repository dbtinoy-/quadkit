"""Database utility helpers for Quadkit."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
import re
from typing import Any

# ISO Date patterns
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?.*$")

# SQL identifier validation (table/column names)
_SQL_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$",
)


def Table(identifier: str) -> str:
    """Validate and quote a SQL identifier.

    Args:
        identifier: The identifier to validate.

    Returns:
        The validated and quoted identifier.

    Raises:
        ValueError: If the identifier is invalid.
    """
    if not identifier:
        raise ValueError("SQL identifier cannot be empty")
    if not _SQL_IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return f'"{identifier}"'


def parse_date_safely(val: Any) -> Any:
    """Safely parse a value into a date or datetime object if it matches common patterns.

    Required for strict drivers like asyncpg.
    """
    if not isinstance(val, str):
        return val

    val = val.strip()
    if not val:
        return None

    # Check for Date (YYYY-MM-DD or YYYY/MM/DD)
    if DATE_PATTERN.match(val) or re.match(r"^\d{4}/\d{2}/\d{2}$", val):
        try:
            clean_val = val.replace("/", "-")
            return datetime.strptime(clean_val, "%Y-%m-%d").date()
        except ValueError:
            return val

    # Check for Datetime (ISO 8601 patterns)
    if "T" in val or re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}", val):
        try:
            # Normalize separator
            clean_val = val.replace(" ", "T").split(".")[0]

            # Handle various lengths
            if len(clean_val) == 16:  # YYYY-MM-DDTHH:MM
                return datetime.strptime(clean_val, "%Y-%m-%dT%H:%M")
            if len(clean_val) == 19:  # YYYY-MM-DDTHH:MM:SS
                return datetime.strptime(clean_val, "%Y-%m-%dT%H:%M:%S")
            if (
                len(clean_val) > 19
            ):  # Handle potential timezone offsets by truncation or specific formats
                try:
                    return datetime.fromisoformat(val)
                except ValueError:
                    return datetime.strptime(clean_val[:19], "%Y-%m-%dT%H:%M:%S")
        except (ValueError, TypeError):
            pass

    return val


def infer_provider_type_from_url(url: str) -> str:
    """Infer canonical provider type from a database URL scheme.

    Examples:
    - "sqlite+aiosqlite:///db" -> "sqlite"
    - "postgresql://user@host/db" -> "postgres"
    - "mysql://..." -> "mysql"

    Raises ValueError for unknown/unsupported schemes.
    """
    from urllib.parse import urlparse

    if not isinstance(url, str) or not url:
        raise ValueError("Invalid URL for provider inference")

    scheme = urlparse(url).scheme.split("+")[0].lower()
    _MAP = {
        "sqlite": "sqlite",
        "postgresql": "postgres",
        "postgres": "postgres",
        "mysql": "mysql",
        "mariadb": "mysql",
    }
    try:
        return _MAP[scheme]
    except KeyError as exc:
        raise ValueError(f"Unsupported database scheme: {scheme}") from exc


def entity_to_dict(entity: Any) -> dict[str, Any]:
    """Convert an entity to a dictionary.

    Supports:
    - dict -> shallow copy
    - DomainModel (via .model_dump())
    - Dataclasses (via dataclasses.asdict())
    - Objects with .dict() method
    - Objects with .__dict__

    Excludes private attributes (starting with '_') and '__table_name__'.
    """
    from quadkit.domain import DomainModel

    if isinstance(entity, dict):
        return entity.copy()

    if isinstance(entity, DomainModel):
        # DomainModel (dataclass-based)
        data = entity.model_dump()
        if isinstance(data, dict):
            return {
                k: v
                for k, v in data.items()
                if not k.startswith("_") and k != "__table_name__"
            }

    if is_dataclass(entity) and not isinstance(entity, type):
        data = asdict(entity)
        return {
            k: v
            for k, v in data.items()
            if not k.startswith("_") and k != "__table_name__"
        }

    if hasattr(entity, "dict") and callable(entity.dict):
        data = entity.dict()
        if isinstance(data, dict):
            return {
                k: v
                for k, v in data.items()
                if not k.startswith("_") and k != "__table_name__"
            }

    if hasattr(entity, "__dict__"):
        return {
            k: v
            for k, v in entity.__dict__.items()
            if not k.startswith("_") and k != "__table_name__"
        }

    raise ValueError(f"Cannot convert entity to dict: {type(entity)}")


__all__ = [
    "Table",
    "entity_to_dict",
    "infer_provider_type_from_url",
    "parse_date_safely",
]
