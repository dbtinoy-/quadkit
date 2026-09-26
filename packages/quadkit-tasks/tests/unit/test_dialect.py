"""Unit tests for the SQL placeholder translation dialect helper.

The translator must only rewrite ``?`` placeholder tokens — a ``?``
inside a string literal, quoted identifier, or comment is part of the
SQL text and must stay untouched (otherwise the placeholder numbering
drifts from the bound parameters and the statement breaks).
"""

from __future__ import annotations

import pytest

from quadkit.tasks.dialect import translate_placeholders


@pytest.mark.parametrize(("sql", "dialect", "expected"), [
    # (sql, dialect, expected)
    ("INSERT INTO t (a, b) VALUES (?, ?)", "postgres", "INSERT INTO t (a, b) VALUES ($1, $2)"),
    ("INSERT INTO t (a) VALUES ('what?')", "postgres", "INSERT INTO t (a) VALUES ('what?')"),
    ("INSERT INTO t (a) VALUES ('it''s?')", "postgres", "INSERT INTO t (a) VALUES ('it''s?')"),
    ("SELECT 1 -- how many? \nWHERE a = ?", "postgres", "SELECT 1 -- how many? \nWHERE a = $1"),
    ("SELECT /* q? */ a FROM t WHERE b = ?", "postgres", "SELECT /* q? */ a FROM t WHERE b = $1"),
    ('SELECT "weird?" FROM t', "postgres", 'SELECT "weird?" FROM t'),
    ("INSERT INTO t (a, b) VALUES (?, 'x?') -- note?", "postgres", "INSERT INTO t (a, b) VALUES ($1, 'x?') -- note?"),
    ("SELECT ? FROM t WHERE b = ?", "postgresql", "SELECT $1 FROM t WHERE b = $2"),
    ("INSERT INTO t (a, b) VALUES (?, 'x?')", "mysql", "INSERT INTO t (a, b) VALUES (%s, 'x?')"),
    ("SELECT ? FROM t", "mariadb", "SELECT %s FROM t"),
    ("INSERT INTO t (a) VALUES (?)", "sqlite", "INSERT INTO t (a) VALUES (?)"),
    ("INSERT INTO t (a) VALUES (?)", "oracle", "INSERT INTO t (a) VALUES (?)"),
    ("", "postgres", ""),
    ("SELECT a FROM t", "postgres", "SELECT a FROM t"),
    ("SELECT 'abc? -- x?", "postgres", "SELECT 'abc? -- x?"),
    ("VALUES (?, 'x?')", "postgres", "VALUES ($1, 'x?')"),
    ("VALUES (?,?)", "postgres", "VALUES ($1,$2)"),
    ("SELECT ? -- ?", "postgres", "SELECT $1 -- ?"),
    ("SELECT 1", "", "SELECT 1"),
])
def test_translate_placeholders(sql: str, dialect: str, expected: str) -> None:
    """Placeholder tokens are rewritten; ? inside SQL tokens is not."""
    assert translate_placeholders(sql, dialect) == expected


def test_numbering_stays_aligned_with_parameters() -> None:
    """The N-th converted placeholder maps to the N-th bound parameter."""
    sql = "INSERT INTO t (a, b, c) VALUES (?, 'keep?', ?) /* ? */ WHERE d = ?"
    out = translate_placeholders(sql, "postgres")
    assert out == "INSERT INTO t (a, b, c) VALUES ($1, 'keep?', $2) /* ? */ WHERE d = $3"
    assert out.count("$") == 3
