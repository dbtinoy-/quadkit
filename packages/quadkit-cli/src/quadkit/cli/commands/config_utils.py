"""Pure helpers shared by the Quadkit config commands.

These helpers contain no I/O and no command wiring — only config-dict
transformation logic used by the Typer commands in ``config.py``.
"""

from __future__ import annotations

import re


def _mask_secrets(config: dict[str, object], reveal: bool = False) -> dict[str, object]:
    if reveal:
        return config

    masked_config: dict[str, object] = {}
    for key, value in config.items():
        if isinstance(value, dict):
            masked_config[key] = _mask_secrets(value, reveal)
        elif isinstance(value, str):
            if any(s in key.lower() for s in ["secret", "password", "key", "token"]):
                masked_config[key] = "***"
            else:
                # Regex to find database URLs with passwords
                masked_config[key] = re.sub(r"://[^@]+@", "://***:***@", value)
        else:
            masked_config[key] = value
    return masked_config


def _dict_diff(
    base: dict,
    compare: dict,
    prefix: str = "",
) -> tuple[dict, dict, dict]:
    """Recursively diff two dicts, returning (added, removed, changed) flat dicts."""
    added: dict = {}
    removed: dict = {}
    changed: dict = {}

    all_keys = set(base) | set(compare)
    for key in all_keys:
        full_key = f"{prefix}.{key}" if prefix else key
        if key not in base:
            added[full_key] = compare[key]
        elif key not in compare:
            removed[full_key] = base[key]
        elif isinstance(base[key], dict) and isinstance(compare[key], dict):
            sub_added, sub_removed, sub_changed = _dict_diff(
                base[key], compare[key], prefix=full_key
            )
            added.update(sub_added)
            removed.update(sub_removed)
            changed.update(sub_changed)
        elif base[key] != compare[key]:
            changed[full_key] = (base[key], compare[key])

    return added, removed, changed
