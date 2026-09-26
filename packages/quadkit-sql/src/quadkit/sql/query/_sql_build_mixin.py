"""Build mixin for AsyncQueryBuilder: build() and all _build_* private methods."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.data.identifiers import Table as SQLTable
from quadkit.contracts.data.sql.sql_dialect import SQLDialect
from quadkit.sql.query.sql_types import (
    ConflictAction,
    ParameterizedQuery,
)


class _BuildMixin:
    """SQL construction methods for AsyncQueryBuilder."""

    _table: SQLTable

    def build(self) -> ParameterizedQuery:
        """Build the final parameterized SQL query.

        Returns:
            ParameterizedQuery containing SQL and params.

        Raises:
            ValueError: If building an UPDATE or DELETE without WHERE conditions.
        """
        if self._mode == "select":  # type: ignore[attr-defined]
            return self._build_select()
        if self._mode == "insert":  # type: ignore[attr-defined]
            return self._build_insert()
        if self._mode == "update":  # type: ignore[attr-defined]
            return self._build_update()
        if self._mode == "delete":  # type: ignore[attr-defined]
            return self._build_delete()
        raise ValueError(f"Unknown query mode: {self._mode}")  # type: ignore[attr-defined]

    def _build_select(self) -> ParameterizedQuery:
        """Build a SELECT query with Phase 1 + 2 features."""
        all_params: list[Any] = []
        param_idx = 1

        # CTE prefix
        cte_prefix = ""
        if self._ctes:  # type: ignore[attr-defined]
            cte_parts = []
            has_recursive = any(c.recursive for c in self._ctes)  # type: ignore[attr-defined]
            for cte in self._ctes:  # type: ignore[attr-defined]
                cte_parts.append(f"{cte.name} AS ({cte.query})")
                if cte.params:
                    all_params.extend(cte.params)
                    param_idx += len(cte.params)
            keyword = "WITH RECURSIVE" if has_recursive else "WITH"
            cte_prefix = f"{keyword} {', '.join(cte_parts)} "

        # Build SELECT clause
        select_exprs: list[str] = [str(c) for c in self._selects]  # type: ignore[attr-defined]
        for raw in self._raw_selects:  # type: ignore[attr-defined]
            select_exprs.append(raw.sql)
        # Remove default "*" if raw selects provided and selects is still default
        if self._raw_selects and self._selects == ["*"]:  # type: ignore[attr-defined]
            select_exprs = [raw.sql for raw in self._raw_selects]  # type: ignore[attr-defined]
            if self._selects != ["*"]:  # type: ignore[attr-defined]
                select_exprs = [str(c) for c in self._selects] + select_exprs  # type: ignore[attr-defined]

        # Window functions
        for w in self._windows:  # type: ignore[attr-defined]
            over_parts = []
            if w.partition_by:
                over_parts.append(
                    f"PARTITION BY {', '.join(str(c) for c in w.partition_by)}",
                )
            if w.order_by:
                over_parts.append(f"ORDER BY {w.order_by}")
            over_clause = " ".join(over_parts)
            select_exprs.append(
                f"{w.func} OVER ({over_clause}) AS {w.alias}",
            )

        select_clause = ", ".join(select_exprs)

        # DISTINCT
        if self._distinct:  # type: ignore[attr-defined]
            if self._distinct_on and self._dialect == SQLDialect.POSTGRESQL:  # type: ignore[attr-defined]
                select_clause = f"DISTINCT ON ({', '.join(str(c) for c in self._distinct_on)}) {select_clause}"  # type: ignore[attr-defined]
            else:
                select_clause = f"DISTINCT {select_clause}"

        parts = [f"{cte_prefix}SELECT {select_clause} FROM {self._table}"]  # noqa: S608 -- builder validates all identifiers via Table()/Column() at entry

        # Collect raw select params
        for raw in self._raw_selects:  # type: ignore[attr-defined]
            if raw.params:
                all_params.extend(raw.params)
                param_idx += len(raw.params)

        # JOINs
        parts.extend(
            [f"{j.type.value} JOIN {j.table} ON {j.on}" for j in self._joins],  # type: ignore[attr-defined]
        )

        # WHERE
        where_sql, where_params, param_idx = self._build_where(param_idx)
        if where_sql:
            parts.append(f"WHERE {where_sql}")
            all_params.extend(where_params)

        # GROUP BY
        if self._group_by:  # type: ignore[attr-defined]
            parts.append(f"GROUP BY {', '.join(str(c) for c in self._group_by)}")  # type: ignore[attr-defined]

        # HAVING
        if self._havings:  # type: ignore[attr-defined]
            having_parts = []
            for h in self._havings:  # type: ignore[attr-defined]
                sql, op_params, param_idx = self._operator_registry.apply_operator(  # type: ignore[attr-defined]
                    h.operator,
                    h.column,
                    h.value,
                    param_idx,
                )
                having_parts.append(sql)
                all_params.extend(op_params)
            parts.append("HAVING " + " AND ".join(having_parts))

        # ORDER BY
        order_parts = [
            f"{o.column} {'DESC' if o.desc else 'ASC'}"
            for o in self._orders  # type: ignore[attr-defined]
        ]
        order_parts.extend(self._raw_orders)  # type: ignore[attr-defined]
        if order_parts:
            parts.append("ORDER BY " + ", ".join(order_parts))

        # LIMIT
        if self._limit is not None:  # type: ignore[attr-defined]
            parts.append(f"LIMIT ${param_idx}")
            all_params.append(self._limit)  # type: ignore[attr-defined]
            param_idx += 1

        # OFFSET
        if self._offset is not None:  # type: ignore[attr-defined]
            parts.append(f"OFFSET ${param_idx}")
            all_params.append(self._offset)  # type: ignore[attr-defined]
            param_idx += 1

        # Row-level locking
        if self._lock_mode:  # type: ignore[attr-defined]
            lock_sql = self._lock_mode.value  # type: ignore[attr-defined]
            if self._lock_no_wait:  # type: ignore[attr-defined]
                lock_sql += " NOWAIT"
            elif self._lock_skip_locked:  # type: ignore[attr-defined]
                lock_sql += " SKIP LOCKED"
            parts.append(lock_sql)

        main_query = " ".join(parts)

        # Set operations
        if self._set_operations:  # type: ignore[attr-defined]
            for sop in self._set_operations:  # type: ignore[attr-defined]
                main_query += f" {sop.operation.value} {sop.query}"
                if sop.params:
                    all_params.extend(sop.params)

        return ParameterizedQuery(main_query, tuple(all_params), self._dialect)  # type: ignore[attr-defined]

    def _build_insert(self) -> ParameterizedQuery:
        """Build an INSERT query with ON CONFLICT support."""
        columns = list(self._data.keys())  # type: ignore[attr-defined]
        values = list(self._data.values())  # type: ignore[attr-defined]
        placeholders = [f"${i + 1}" for i in range(len(values))]
        len(values) + 1

        parts = [
            f"INSERT INTO {self._table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",  # noqa: S608 -- builder validates all identifiers via Table()/Column() at entry  # type: ignore[attr-defined]
        ]

        # ON CONFLICT
        if self._conflict_columns and self._conflict_action:  # type: ignore[attr-defined]
            conflict_cols = ", ".join(self._conflict_columns)  # type: ignore[attr-defined]
            if self._conflict_action == ConflictAction.DO_NOTHING:  # type: ignore[attr-defined]
                parts.append(f"ON CONFLICT ({conflict_cols}) DO NOTHING")
            elif self._conflict_action == ConflictAction.DO_UPDATE:  # type: ignore[attr-defined]
                update_cols = self._conflict_update_columns or [  # type: ignore[attr-defined]
                    c
                    for c in columns
                    if c not in self._conflict_columns  # type: ignore[attr-defined]
                ]
                set_parts = [f"{col} = EXCLUDED.{col}" for col in update_cols]
                parts.append(
                    f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {', '.join(set_parts)}",
                )

        if self._returning:  # type: ignore[attr-defined]
            parts.append(f"RETURNING {', '.join(self._returning)}")  # type: ignore[attr-defined]

        return ParameterizedQuery(" ".join(parts), tuple(values), self._dialect)  # type: ignore[attr-defined]

    def _build_update(self) -> ParameterizedQuery:
        """Build an UPDATE query."""
        if not self._wheres and not self._raw_wheres:  # type: ignore[attr-defined]
            raise ValueError(
                "UPDATE queries must have WHERE conditions to prevent accidental mass updates",
            )

        set_parts = []
        params = []
        param_idx = 1

        sorted_keys = sorted(self._data.keys())  # type: ignore[attr-defined]
        for key in sorted_keys:
            set_parts.append(f"{key} = ${param_idx}")
            params.append(self._data[key])  # type: ignore[attr-defined]
            param_idx += 1

        parts = [f"UPDATE {self._table} SET {', '.join(set_parts)}"]  # noqa: S608 -- builder validates all identifiers via Table()/Column() at entry  # type: ignore[attr-defined]

        where_sql, where_params, _next_idx = self._build_where(param_idx)
        if where_sql:
            parts.append(f"WHERE {where_sql}")
            params.extend(where_params)

        if self._returning:  # type: ignore[attr-defined]
            parts.append(f"RETURNING {', '.join(self._returning)}")  # type: ignore[attr-defined]

        return ParameterizedQuery(" ".join(parts), tuple(params), self._dialect)  # type: ignore[attr-defined]

    def _build_delete(self) -> ParameterizedQuery:
        """Build a DELETE query."""
        if not self._wheres and not self._raw_wheres:  # type: ignore[attr-defined]
            raise ValueError(
                "DELETE queries must have WHERE conditions to prevent accidental mass deletions",
            )

        parts = [f"DELETE FROM {self._table}"]  # noqa: S608 -- builder validates all identifiers via Table()/Column() at entry  # type: ignore[attr-defined]
        params = []
        param_idx = 1

        where_sql, where_params, _next_idx = self._build_where(param_idx)
        if where_sql:
            parts.append(f"WHERE {where_sql}")
            params.extend(where_params)

        if self._returning:  # type: ignore[attr-defined]
            parts.append(f"RETURNING {', '.join(self._returning)}")  # type: ignore[attr-defined]

        return ParameterizedQuery(" ".join(parts), tuple(params), self._dialect)  # type: ignore[attr-defined]

    def _build_where(self, start_idx: int) -> tuple[str, list[Any], int]:
        """Build WHERE clause from AND, OR, raw, and subquery conditions."""
        if (
            not self._wheres  # type: ignore[attr-defined]
            and not self._or_wheres  # type: ignore[attr-defined]
            and not self._raw_wheres  # type: ignore[attr-defined]
            and not self._subquery_wheres  # type: ignore[attr-defined]
        ):
            return "", [], start_idx

        and_parts = []
        params = []
        current_idx = start_idx

        # Standard AND conditions
        for w in self._wheres:  # type: ignore[attr-defined]
            sql, op_params, current_idx = self._operator_registry.apply_operator(  # type: ignore[attr-defined]
                w.operator,
                w.column,
                w.value,
                current_idx,
            )
            and_parts.append(sql)
            params.extend(op_params)

        # Raw WHERE expressions
        for raw in self._raw_wheres:  # type: ignore[attr-defined]
            and_parts.append(raw.sql)
            if raw.params:
                params.extend(raw.params)
                current_idx += len(raw.params)

        # Subquery WHERE expressions (IN, EXISTS, etc.)
        for sq in self._subquery_wheres:  # type: ignore[attr-defined]
            and_parts.append(sq.sql)
            if sq.params:
                params.extend(sq.params)
                current_idx += len(sq.params)

        # OR conditions
        or_parts = []
        for o in self._or_wheres:  # type: ignore[attr-defined]
            sql, op_params, current_idx = self._operator_registry.apply_operator(  # type: ignore[attr-defined]
                o.operator,
                o.column,
                o.value,
                current_idx,
            )
            or_parts.append(sql)
            params.extend(op_params)

        # Combine: (AND_part1 AND AND_part2) OR or_part1 OR or_part2
        if and_parts and or_parts:
            and_clause = " AND ".join(and_parts)
            result = f"({and_clause}) OR " + " OR ".join(or_parts)
        elif and_parts:
            result = " AND ".join(and_parts)
        elif or_parts:
            result = " OR ".join(or_parts)
        else:
            return "", [], current_idx

        return result, params, current_idx
