"""Query analyzer with EXPLAIN plan support and N+1 detection.

Provides tools for optimizing query performance:
- Execute EXPLAIN/EXPLAIN ANALYZE
- Detect N+1 query patterns from recent query logs
- Suggest missing indexes based on slow query analysis

Example:
    from quadkit.logging import get_logger

    logger = get_logger(__name__)
    analyzer = QueryAnalyzer(provider)

    plan = await analyzer.explain("SELECT * FROM users WHERE email = $1", ["a@b.com"])
    logger.info("query_plan", cost=plan.estimated_cost, scan_type=plan.scan_type)

    detections = analyzer.detect_n_plus_one(recent_queries)
    for d in detections:
        logger.info("n_plus_one_detected", parent=d.parent_query, child=d.child_query, count=d.count)
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueryPlan:
    """Parsed query execution plan."""

    raw_plan: Any
    estimated_cost: float = 0.0
    actual_time_ms: float | None = None
    scan_type: str = ""  # Seq Scan, Index Scan, Bitmap, etc.
    rows_estimated: int = 0
    rows_actual: int | None = None
    index_used: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def uses_seq_scan(self) -> bool:
        return "Seq Scan" in self.scan_type

    @property
    def is_slow(self) -> bool:
        return self.estimated_cost > 1000 or (
            self.actual_time_ms is not None and self.actual_time_ms > 100
        )


@dataclass
class IndexSuggestion:
    """Suggested index for query optimization."""

    table: str
    columns: list[str]
    reason: str
    estimated_improvement: str  # "high", "medium", "low"

    def to_sql(self, dialect: str = "postgresql") -> str:
        cols = ", ".join(self.columns)
        idx_name = f"idx_{self.table}_{'_'.join(self.columns)}"
        concurrently = " CONCURRENTLY" if dialect == "postgresql" else ""
        return f"CREATE INDEX{concurrently} {idx_name} ON {self.table} ({cols})"


@dataclass
class NPlusOneDetection:
    """Detected N+1 query pattern."""

    parent_query: str
    child_query: str
    count: int
    suggestion: str


class QueryAnalyzer:
    """Analyze query execution plans for optimization."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def explain(
        self,
        sql: str,
        params: list[Any] | None = None,
        *,
        analyze: bool = False,
        format_type: str = "json",
    ) -> QueryPlan:
        """Execute EXPLAIN (ANALYZE) on a query.

        Args:
            sql: The SQL query to explain.
            params: Query parameters.
            analyze: If True, actually execute the query (EXPLAIN ANALYZE).
            format_type: Output format ("json", "text", "yaml").

        Returns:
            Parsed QueryPlan.
        """
        explain_prefix = "EXPLAIN"
        options: list[str] = []

        if analyze:
            options.append("ANALYZE")
        if format_type != "text":
            options.append(f"FORMAT {format_type.upper()}")

        if options:
            explain_sql = f"{explain_prefix} ({', '.join(options)}) {sql}"
        else:
            explain_sql = f"{explain_prefix} {sql}"

        try:
            result = await self._provider.execute(
                explain_sql,
                params or [],
            )
            return self._parse_plan(result, analyze=analyze)
        except Exception as exc:  # noqa: BLE001 — any EXPLAIN failure degrades to a warning plan
            logger.warning("EXPLAIN failed: %s", exc)
            return QueryPlan(
                raw_plan=str(exc),
                warnings=[f"EXPLAIN failed: {exc}"],
            )

    def _parse_plan(
        self,
        raw_result: Any,
        *,
        analyze: bool = False,
    ) -> QueryPlan:
        """Parse the raw EXPLAIN output into a QueryPlan."""
        plan = QueryPlan(raw_plan=raw_result)
        warnings: list[str] = []

        if isinstance(raw_result, list) and raw_result:
            first = raw_result[0]

            # JSON format
            if isinstance(first, dict):
                node = first.get("Plan", first)
                plan.scan_type = node.get("Node Type", "")
                plan.estimated_cost = node.get(
                    "Total Cost",
                    0.0,
                )
                plan.rows_estimated = node.get("Plan Rows", 0)
                plan.index_used = node.get("Index Name")

                if analyze:
                    plan.actual_time_ms = node.get("Actual Total Time")
                    plan.rows_actual = node.get("Actual Rows")

            # Text format
            elif isinstance(first, (str, tuple)):
                text = str(first)
                if "Seq Scan" in text:
                    plan.scan_type = "Seq Scan"
                    warnings.append(
                        "Sequential scan detected — consider adding an index",
                    )
                elif "Index Scan" in text:
                    plan.scan_type = "Index Scan"
                elif "Bitmap" in text:
                    plan.scan_type = "Bitmap Scan"

                # Extract cost
                cost_match = re.search(
                    r"cost=[\d.]+\.\.([\d.]+)",
                    text,
                )
                if cost_match:
                    plan.estimated_cost = float(cost_match.group(1))

        if plan.uses_seq_scan and plan.rows_estimated > 1000:
            warnings.append(
                "Sequential scan on large table — index recommended",
            )

        plan.warnings = warnings
        return plan

    @staticmethod
    def detect_n_plus_one(
        recent_queries: list[dict[str, Any]],
        *,
        threshold: int = 5,
    ) -> list[NPlusOneDetection]:
        """Detect N+1 query patterns from recent query logs.

        Looks for repeated similar queries that differ only
        in parameter values, suggesting they should be batched.

        Args:
            recent_queries: List of dicts with "sql" and optionally "params".
            threshold: Minimum repetitions to flag as N+1.

        Returns:
            List of detected N+1 patterns.
        """
        # Normalize queries by replacing parameter placeholders
        normalized: Counter[str] = Counter()
        raw_sql_map: dict[str, str] = {}

        for q in recent_queries:
            sql = q.get("sql", "")
            # Normalize: replace $1, $2, %s, ? with ?
            norm = re.sub(r"\$\d+|%s|\?", "?", sql).strip()
            normalized[norm] += 1
            raw_sql_map[norm] = sql

        detections: list[NPlusOneDetection] = []
        for pattern, count in normalized.most_common():
            if count >= threshold:
                # Try to identify parent/child relationship
                detections.append(
                    NPlusOneDetection(
                        parent_query="(check calling code)",
                        child_query=raw_sql_map[pattern][:200],
                        count=count,
                        suggestion=(
                            f"Query executed {count} times — "
                            f"consider using JOIN, IN(), or batch loading"
                        ),
                    ),
                )

        return detections

    @staticmethod
    def suggest_indexes(
        slow_queries: list[dict[str, Any]],
    ) -> list[IndexSuggestion]:
        """Suggest indexes based on slow query analysis.

        Args:
            slow_queries: List of dicts with "sql" and "duration_ms".

        Returns:
            List of index suggestions.
        """
        suggestions: list[IndexSuggestion] = []
        table_column_freq: dict[str, Counter[str]] = defaultdict(Counter)

        for q in slow_queries:
            sql = q.get("sql", "")

            # Extract table and WHERE columns
            table_match = re.search(
                r"FROM\s+[\"']?(\w+)[\"']?",
                sql,
                re.IGNORECASE,
            )
            where_cols = re.findall(
                r"WHERE\s+.*?[\"']?(\w+)[\"']?\s*[=<>!]",
                sql,
                re.IGNORECASE,
            )

            if table_match and where_cols:
                table = table_match.group(1)
                for col in where_cols:
                    table_column_freq[table][col] += 1

        for table, col_counts in table_column_freq.items():
            for col, freq in col_counts.most_common(3):
                if freq >= 3:
                    suggestions.append(
                        IndexSuggestion(
                            table=table,
                            columns=[col],
                            reason=(
                                f"Column '{col}' used in WHERE clause "
                                f"{freq} times in slow queries"
                            ),
                            estimated_improvement=("high" if freq >= 10 else "medium"),
                        ),
                    )

        return suggestions
