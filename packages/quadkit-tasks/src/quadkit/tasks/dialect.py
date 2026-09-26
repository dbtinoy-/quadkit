"""SQL placeholder translation for store-backed persistence.

The lightweight durable stores (workflow state, scheduler definitions) are
written against the SQLite ``?`` placeholder style.  Providers such as
``PostgresProvider`` use ``$1``-style placeholders, so the stores translate
the placeholder *style* based on the provider's dialect name (a best-effort
attribute, defaulting to SQLite when absent).

Only placeholder syntax is translated.  Dialect-specific statement syntax
(e.g. MySQL's ``ON DUPLICATE KEY UPDATE`` instead of ``ON CONFLICT``) is out
of scope: these stores support SQLite and PostgreSQL.
"""

from __future__ import annotations

_POSTGRES_DIALECTS = {"postgres", "postgresql"}
_MYSQL_DIALECTS = {"mysql", "mariadb"}

__all__ = ["translate_placeholders"]


def _skip_string(sql: str, i: int) -> int:
    """Index just past the single-quoted literal starting at ``sql[i]``.

    ``''`` is an escaped quote and stays inside the literal. An
    unterminated literal consumes to the end of the statement.
    """
    n = len(sql)
    j = i + 1
    while j < n:
        if sql[j] == "'":
            if j + 1 < n and sql[j + 1] == "'":
                j += 2  # escaped quote — still inside the literal
                continue
            return j + 1
        j += 1
    return n


def translate_placeholders(sql: str, dialect: str) -> str:
    """Rewrite ``?`` placeholders for the target dialect.

    Placeholder detection skips single-quoted string literals (including
    ``''`` escapes), double-quoted identifiers, line comments (``--``)
    and block comments (``/* ... */``), so a ``?`` inside any of those
    is left untouched and the placeholder numbering stays aligned with
    the bound parameters.

    Args:
        sql: SQL statement using ``?`` placeholders.
        dialect: Provider dialect name (e.g. ``"postgres"``,
            ``"sqlite"``). Unknown or empty dialects pass through
            unchanged (SQLite style).

    Returns:
        The statement with placeholders adapted to the dialect.
    """
    postgres = dialect in _POSTGRES_DIALECTS
    if not postgres and dialect not in _MYSQL_DIALECTS:
        return sql
    parts: list[str] = []
    index = 1
    i = 0
    n = len(sql)
    while i < n:
        char = sql[i]
        if char == "'":
            start = i
            i = _skip_string(sql, i)
        elif char == '"':
            start = i
            end = sql.find('"', i + 1)
            i = n if end == -1 else end + 1
        elif sql.startswith("--", i):
            start = i
            end = sql.find("\n", i)
            i = n if end == -1 else end  # newline reprocessed by the loop
        elif sql.startswith("/*", i):
            start = i
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            if char == "?":
                parts.append(f"${index}" if postgres else "%s")
                index += 1
            else:
                parts.append(char)
            i += 1
            continue
        parts.append(sql[start:i])
    return "".join(parts)
