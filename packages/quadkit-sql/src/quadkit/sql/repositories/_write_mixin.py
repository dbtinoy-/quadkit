"""Write mixin for SQLRepository: create, update, delete, upsert."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, NoReturn, cast
from uuid import UUID

from quadkit.contracts.data.identifiers import Column
from quadkit.contracts.data.sql.database import provider_dialect
from quadkit.logging import get_logger, safe_error_type
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import (
    CheckConstraintError,
    DatabaseConnectionError,
    DatabaseError,
    DuplicateKeyError,
    ForeignKeyError,
    IntegrityError,
    NotNullViolationError,
    QueryError,
    RepositoryError,
    TenantScopingError,
)

logger = get_logger(__name__)

#: Driver message fragments that identify *which* integrity rule a failed
#: write broke.
#:
#: ``DatabaseProviderProtocol.execute_insert`` reports failure as a result
#: (``success=False``, ``error_message=str(exc)``), not as an exception, so the
#: provider's exception type is gone by the time the repository sees it — only
#: the driver's text survives. Reconstructing the class from that text is the
#: one honest option left, and doing it here rather than at each call site
#: means every caller can catch ``DuplicateKeyError`` instead of matching
#: strings. Patterns are the ones SQLite, Postgres, MySQL/MariaDB and SQL Server
#: emit for the same four violations.
_INTEGRITY_SIGNATURES: tuple[tuple[tuple[str, ...], type[Exception]], ...] = (
    (
        (
            "unique constraint",
            "duplicate key",
            "duplicate entry",
            "unique failed",
            "already exists",
        ),
        DuplicateKeyError,
    ),
    (
        (
            "foreign key constraint",
            "violates foreign key",
            "cannot add or update a child row",
        ),
        ForeignKeyError,
    ),
    (
        ("not null constraint", "null value in column", "cannot be null"),
        NotNullViolationError,
    ),
    (
        ("check constraint", "violates check constraint"),
        CheckConstraintError,
    ),
)


def _raise_write_failure(message: str, operation: str = "Insert") -> NoReturn:
    """Raise the typed error a failed write's driver message describes.

    The integrity signatures are properties of the *statement*, not of the
    operation that issued it: a unique index on ``name`` rejects a duplicate
    just as loudly through ``UPDATE … SET name = ?`` as through ``INSERT``. The
    insert path has classified its failures for a while; the update paths did
    not, so a caller renaming a row onto a taken name saw a generic
    ``RepositoryError`` and could only tell "that name is taken" from "the
    database is down" by matching driver text itself.

    Args:
        message: The provider's ``error_message`` for the failed statement.
        operation: What was being attempted, for the fallback message.

    Raises:
        RepositoryError: Or one of its integrity subclasses, when the message
            names a constraint violation.
    """
    lowered = (message or "").lower()
    for signatures, error_type in _INTEGRITY_SIGNATURES:
        if any(signature in lowered for signature in signatures):
            raise error_type(message)
    raise RepositoryError(
        f"{operation} failed: {message}" if message else f"{operation} failed"
    )


class _WriteMixin:
    """Provides ``create``, ``update``, ``soft_delete``, ``delete_by_id``,
    ``delete_where`` and ``upsert``."""

    _TEXT_COLUMN_TYPES: frozenset[str] = frozenset(
        {
            "character varying",
            "character",
            "varchar",
            "char",
            "bpchar",
            "text",
            "nvarchar",
        }
    )

    def _timestamp_for_column(self, col_name: str, ts: datetime) -> datetime:
        """Align *ts* timezone awareness with the resolved SQL column type."""
        col_types = getattr(self, "_table_column_types", None) or {}
        if (
            col_types.get(col_name) == "timestamp without time zone"
            and ts.tzinfo is not None
        ):
            return ts.astimezone(UTC).replace(tzinfo=None)
        return ts

    def _coerce_column_types(self, data: dict[str, Any]) -> dict[str, Any]:
        """Align Python values with resolved SQL column types (e.g. UUID -> str on VARCHAR)."""
        col_types = getattr(self, "_table_column_types", None) or {}
        if not col_types:
            return data
        for col_name, value in list(data.items()):
            if isinstance(value, UUID):
                base_type = col_types.get(col_name, "").split("(", 1)[0].strip()
                if base_type in self._TEXT_COLUMN_TYPES:
                    data[col_name] = str(value)
        return data

    async def _stamps_updated_at(self) -> bool:
        """Whether the table has an ``updated_at`` column to stamp.

        ``update`` used to write ``updated_at`` unconditionally, which fails the
        same way ``create`` did on a table that keeps no audit column — the
        UPDATE names a column the table does not have. The schema decides, once
        per repository; an unresolvable schema keeps the old behaviour.
        """
        columns = await self.table_columns()  # type: ignore[attr-defined]
        return columns is None or "updated_at" in columns

    async def _stamped(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add the audit timestamps *data* omits and the table actually has.

        Both write paths stamp the same two columns, and both must skip the
        ones the table does not define — see :meth:`SQLRepository.table_columns`
        for why stamping an absent column is a hard failure rather than a
        harmless extra field.

        Args:
            data: The row about to be written; mutated in place.

        Returns:
            The same mapping, for call chaining.
        """
        columns = await self.table_columns()  # type: ignore[attr-defined]
        self._coerce_column_types(data)
        now = ambient_clock.now()
        for name in ("created_at", "updated_at"):
            if data.get(name) is not None:
                if isinstance(data[name], datetime):
                    data[name] = self._timestamp_for_column(name, data[name])
                continue
            if columns is None or name in columns:
                data[name] = self._timestamp_for_column(name, now)
            else:
                data.pop(name, None)
        return data

    async def create(self, entity: Any) -> Any:
        """Insert *entity* into the database.

        Args:
            entity: Entity to insert.

        Returns:
            The entity with the generated primary key set.

        Raises:
            RepositoryError: On database failure.
            IntegrityError: On constraint violation (foreign key, unique,
                NOT NULL, CHECK). Constraint outcomes propagate typed so
                callers can answer for them instead of receiving a
                wrapped, indistinguishable failure.
        """
        try:
            data = await self._stamped(
                self._entity_to_dict(entity)  # type: ignore[attr-defined]
            )

            if self.multi_tenant:  # type: ignore[attr-defined]
                active_tenant = (
                    self._db_ctx.tenant_id if self._db_ctx is not None else None  # type: ignore[attr-defined]
                )
                supplied = data.get("tenant_id")
                if active_tenant is None:
                    raise TenantScopingError(
                        table=self.table_name,  # type: ignore[attr-defined]
                        operation="INSERT",
                    )
                if supplied is None:
                    data["tenant_id"] = active_tenant
                elif supplied != active_tenant:
                    raise TenantScopingError(
                        table=self.table_name,  # type: ignore[attr-defined]
                        operation="INSERT",
                    )

            if self.key_field not in data or data.get(self.key_field) is None:  # type: ignore[attr-defined]
                data.pop(self.key_field, None)  # type: ignore[attr-defined]

            for field in self.read_only_fields:  # type: ignore[attr-defined]
                if field in data:
                    del data[field]

            self._rls_validate_insert(data)  # type: ignore[attr-defined]

            result = await self.provider.execute_insert(self.write_table_name, data)  # type: ignore[attr-defined]
            if not result.success:
                _raise_write_failure(result.error_message or "")
            # Assign the generated key only when the caller did not supply one.
            # ``inserted_id`` is the driver's ``lastrowid``, which for a table
            # whose primary key the caller chose (a user id, a uuid) is the
            # SQLite rowid: assigning it would replace the real key on the
            # in-memory entity, so the caller would hold a different identity
            # from the row it just inserted.
            key_supplied = self.key_field in data  # type: ignore[attr-defined]
            if result.success and result.inserted_id and not key_supplied:
                if isinstance(entity, dict):
                    entity[self.key_field] = result.inserted_id  # type: ignore[attr-defined]
                else:
                    setattr(entity, self.key_field, result.inserted_id)  # type: ignore[attr-defined]

            for hook in getattr(self, "_post_save_hooks", []):
                await hook(entity)
            return entity
        except TenantScopingError:
            raise
        except RepositoryError:
            # RepositoryError (and the integrity subclasses ``create`` raises
            # for a constraint violation) carry the reason the insert failed —
            # "this key already exists", "this column is not nullable". Wrapping
            # them in a generic message would throw that away and leave callers
            # matching driver strings to tell a duplicate from an outage.
            raise
        except IntegrityError:
            # The integrity subclasses are not RepositoryErrors, so without
            # this they would fall through to the catch-all below and lose the
            # distinction ``_raise_insert_failure`` just made.
            raise
        except (
            DatabaseError,
            QueryError,
            ForeignKeyError,
            DatabaseConnectionError,
        ) as err:
            logger.error(
                "repository_create_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to create entity") from err

    async def update(self, entity: Any, check_version: bool | None = None) -> Any:
        """Update an existing *entity* in the database.

        Args:
            entity: Entity with updated fields; must have a primary key.
            check_version: If True, enforce optimistic locking using entity.version.
                If False, skip optimistic locking even for versioned entities.
                If None (default), automatically enable locking if entity has a version attribute.

        Returns:
            The updated entity.

        Raises:
            RepositoryError: If primary key is missing or update fails.
            OptimisticLockError: If version check fails (for versioned entities by
                default, or when check_version=True).
            ValueError: If check_version=True but entity has no version attribute.
        """
        should_check_version = (
            check_version if check_version is not None else hasattr(entity, "version")
        )
        if should_check_version:
            return await self._execute_versioned_update(entity)
        return await self._execute_standard_update(entity)

    async def _execute_standard_update(self, entity: Any) -> Any:
        data = self._entity_to_dict(entity)  # type: ignore[attr-defined]
        if isinstance(entity, dict):
            key_value = entity.get(self.key_field)  # type: ignore[attr-defined]
        else:
            key_value = getattr(entity, self.key_field, None)  # type: ignore[attr-defined]

        if key_value is None:
            raise RepositoryError("Entity must have a primary key value for update")

        if await self._stamps_updated_at():
            data["updated_at"] = self._timestamp_for_column(
                "updated_at", ambient_clock.now()
            )
        self._coerce_column_types(data)

        if self.key_field in data:  # type: ignore[attr-defined]
            del data[self.key_field]  # type: ignore[attr-defined]

        for field in self.read_only_fields:  # type: ignore[attr-defined]
            if field in data:
                del data[field]

        try:
            param_key = str(key_value) if isinstance(key_value, UUID) else key_value
            where_clause = f"{self._key_col} = ?"  # type: ignore[attr-defined]
            where_params: list[Any] = [param_key]
            # Append RLS scope to UPDATE WHERE clause
            _dummy = f"UPDATE _ SET _ WHERE {where_clause}"  # noqa: S608 -- where-clause from Column()-validated self._key_col, values parameterized
            _dummy, where_params = self._rls_apply(_dummy, where_params, "UPDATE")  # type: ignore[attr-defined]
            # Extract only the part after WHERE (provider takes a where_clause string)
            where_clause = _dummy.split(" WHERE ", 1)[1]
            result = await self.provider.execute_update(  # type: ignore[attr-defined]
                self.write_table_name,  # type: ignore[attr-defined]
                data,
                where_clause,
                where_params,
            )

            if not result.success:
                _raise_write_failure(result.error_message or "", "Update")

            for hook in getattr(self, "_post_save_hooks", []):
                await hook(entity)
            return entity
        except (RepositoryError, IntegrityError):
            raise
        except (DatabaseError, QueryError, DatabaseConnectionError) as err:
            logger.error(
                "repository_update_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to update entity") from err

    async def _execute_versioned_update(self, entity: Any) -> Any:
        from quadkit.sql.exceptions import OptimisticLockError

        data = self._entity_to_dict(entity)  # type: ignore[attr-defined]
        if isinstance(entity, dict):
            key_value = entity.get(self.key_field)  # type: ignore[attr-defined]
        else:
            key_value = getattr(entity, self.key_field, None)  # type: ignore[attr-defined]

        if key_value is None:
            raise RepositoryError("Entity must have a primary key value for update")

        if await self._stamps_updated_at():
            data["updated_at"] = self._timestamp_for_column(
                "updated_at", ambient_clock.now()
            )
        self._coerce_column_types(data)

        if self.key_field in data:  # type: ignore[attr-defined]
            del data[self.key_field]  # type: ignore[attr-defined]

        for field in self.read_only_fields:  # type: ignore[attr-defined]
            if field in data:
                del data[field]

        if not hasattr(entity, "version"):
            raise ValueError(
                "Entity must have a 'version' attribute for optimistic locking."
            )
        current_version = entity.version
        if not isinstance(current_version, int):
            raise TypeError(
                "Entity 'version' attribute must be an int for optimistic locking."
            )
        data["version"] = current_version + 1
        try:
            param_key = str(key_value) if isinstance(key_value, UUID) else key_value
            where_clause_v = f"{self._key_col} = ? AND version = ?"  # type: ignore[attr-defined]
            where_params_v: list[Any] = [param_key, current_version]
            _dummy_v = f"UPDATE _ SET _ WHERE {where_clause_v}"  # noqa: S608 -- where-clause from Column()-validated self._key_col, values parameterized
            _dummy_v, where_params_v = self._rls_apply(  # type: ignore[attr-defined]
                _dummy_v, where_params_v, "UPDATE"
            )
            where_clause_v = _dummy_v.split(" WHERE ", 1)[1]
            result = await self.provider.execute_update(  # type: ignore[attr-defined]
                self.write_table_name,  # type: ignore[attr-defined]
                data,
                where_clause_v,
                where_params_v,
            )
            affected = getattr(result, "affected_rows", None)
            if affected == 0 or not result.success:
                raise OptimisticLockError(
                    type(entity).__name__, param_key, current_version
                )
            entity.version = current_version + 1
            for hook in getattr(self, "_post_save_hooks", []):
                await hook(entity)
            return entity
        except OptimisticLockError:
            raise
        except (RepositoryError, IntegrityError):
            raise
        except (DatabaseError, QueryError, DatabaseConnectionError) as err:
            logger.error(
                "repository_versioned_update_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to update entity (optimistic lock)") from err

    async def soft_delete(self, key: Any) -> bool:
        """Mark entity as deleted without removing it from the database.

        Args:
            key: Primary key of the entity to soft-delete.

        Returns:
            ``True`` if the operation succeeded.

        Raises:
            RepositoryError: On database failure.
            IntegrityError: On constraint violation (propagates typed).
        """
        try:
            data = {"deleted_at": ambient_clock.now()}
            param_key = str(key) if isinstance(key, UUID) else key
            result = await self.provider.execute_update(  # type: ignore[attr-defined]
                self.write_table_name,  # type: ignore[attr-defined]
                data,
                f"{self._key_col} = ?",  # type: ignore[attr-defined]
                [param_key],
            )
            return cast("bool", result.success)
        except IntegrityError:
            raise
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
        ) as err:
            logger.error(
                "repository_soft_delete_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to soft delete entity") from err

    async def delete_by_id(self, key: Any) -> bool:
        """Delete entity by primary key.

        Args:
            key: Primary key of the entity to delete.

        Returns:
            ``True`` if an entity was deleted.

        Raises:
            RepositoryError: On database failure.
            IntegrityError: On constraint violation (propagates typed).
        """
        try:
            del_where = f"{self._key_col} = ?"  # type: ignore[attr-defined]
            del_params: list[Any] = [key]
            _dummy_d = f"DELETE FROM _ WHERE {del_where}"  # noqa: S608 -- where-clause from Column()-validated self._key_col, values parameterized
            _dummy_d, del_params = self._rls_apply(_dummy_d, del_params, "DELETE")  # type: ignore[attr-defined]
            del_where = _dummy_d.split(" WHERE ", 1)[1]
            result = await self.provider.execute_delete(  # type: ignore[attr-defined]
                self.write_table_name,  # type: ignore[attr-defined]
                del_where,
                del_params,
            )
            if not result.success:
                raise RepositoryError(f"Delete failed: {result.error_message}")

            affected = getattr(result, "affected_rows", None)
            if isinstance(affected, int):
                return affected > 0

            return True
        except (RepositoryError, IntegrityError):
            raise
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
        ) as err:
            logger.exception(
                "Failed delete_by_id table=%s key=%s",
                self.table_name,  # type: ignore[attr-defined]
                key,
            )
            raise RepositoryError("Failed to delete entity") from err

    async def update_where(
        self,
        data: Mapping[str, Any],
        *filter_expressions: Any,
        **filters: Any,
    ) -> int:
        """Update every row matching the filters and return how many changed.

        ``update`` keys the row by its primary key. A conditional write —
        "advance this task, but only while *this* worker still holds it" — has
        no primary key to give, and writing it by hand puts the ownership
        check outside the filter builder. The filters here are the ones
        ``find_many`` accepts, and the statement goes through the provider's
        ``execute_update`` so the affected-row count is the driver's.

        A value may be a
        :class:`~quadkit.contracts.data.identifiers.Delta`, which moves the
        column relative to itself (``SET quota = quota + ?``) instead of
        assigning to it. That is the statement a balance needs: read the row,
        add in the caller and write back is two statements and a lost update
        when two operators act at once.

        Args:
            data: Column values to write, or ``Delta`` moves.
            *filter_expressions: Typed ``Filter`` expressions to AND together.
            **filters: Keyword equality filters, as in ``find_many``.

        Returns:
            Number of rows the driver reported as updated. Zero is a real
            answer, not a failure: it means the filters matched nothing (for
            example, another worker owns the row now).

        Raises:
            RepositoryError: When *data* is empty or no filter is supplied —
                either would rewrite every row in the table.
            RepositoryError: On database failure.
        """
        if not data:
            raise RepositoryError("update_where requires at least one column value")
        try:
            params: list[Any] = []
            statement = await self._apply_filters_to_query(  # type: ignore[attr-defined]
                "UPDATE _",  # noqa: S608 -- placeholder table, replaced by execute_update
                params,
                dict(filters),
                True,
                filter_expressions,
            )
            if " WHERE " not in statement:
                # No filter means every row: refuse rather than let a missing
                # argument rewrite the table.
                raise RepositoryError("update_where requires at least one filter")
            statement, params = self._rls_apply(statement, params, "UPDATE")  # type: ignore[attr-defined]
            where_clause = statement.split(" WHERE ", 1)[1]
            result = await self.provider.execute_update(  # type: ignore[attr-defined]
                self.write_table_name,  # type: ignore[attr-defined]
                dict(data),
                where_clause,
                params,
            )
            if not result.success:
                _raise_write_failure(result.error_message or "", "Update")
            return int(getattr(result, "affected_rows", 0) or 0)
        except RepositoryError:
            raise
        except IntegrityError:
            # The integrity subclasses carry *which* rule the statement broke —
            # "that name is taken", "that column is not nullable". Folding them
            # into a generic failure would leave the caller matching driver
            # text, which is the thing the classification exists to prevent.
            raise
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
        ) as err:
            logger.error(
                "repository_update_where_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to update entities") from err

    async def delete_where(
        self,
        *filter_expressions: Any,
        include_deleted: bool = False,
        **filters: Any,
    ) -> int:
        """Delete every row matching the filters and return how many went.

        ``delete_by_id`` is the only removal a repository offered before this,
        so a host that needed "drop the rows older than X" wrote the DELETE by
        hand — outside the filter builder, outside row-level security, and
        outside the dialect handling. The filters here are the same ones
        ``find_many`` accepts (typed ``Filter`` expressions or keyword
        equality), and the statement goes through the provider's
        ``execute_delete`` so the affected-row count is the driver's.

        Args:
            *filter_expressions: Typed ``Filter`` expressions to AND together.
            include_deleted: Also remove soft-deleted rows. Defaults to
                ``False``, matching ``find_many``: a soft-delete table keeps
                its tombstones out of a filtered purge unless asked.
            **filters: Keyword equality filters, as in ``find_many``.

        Returns:
            Number of rows the driver reported as deleted.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            params: list[Any] = []
            statement = await self._apply_filters_to_query(  # type: ignore[attr-defined]
                "DELETE FROM _",  # noqa: S608 -- placeholder table, replaced by execute_delete
                params,
                dict(filters),
                include_deleted,
                filter_expressions,
            )
            if " WHERE " not in statement:
                # A repository must not offer "delete everything": an empty
                # filter is a bug at the call site, and a caller that really
                # means a purge can say so with an explicit filter.
                raise RepositoryError("delete_where requires at least one filter")
            statement, params = self._rls_apply(statement, params, "DELETE")  # type: ignore[attr-defined]
            where_clause = statement.split(" WHERE ", 1)[1]
            result = await self.provider.execute_delete(  # type: ignore[attr-defined]
                self.write_table_name,  # type: ignore[attr-defined]
                where_clause,
                params,
            )
            if not result.success:
                raise RepositoryError(f"Delete failed: {result.error_message}")
            affected = getattr(result, "affected_rows", 0)
            return int(affected or 0)
        except RepositoryError:
            raise
        except (
            DatabaseError,
            QueryError,
            ForeignKeyError,
            DatabaseConnectionError,
        ) as err:
            logger.error(
                "repository_delete_where_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to delete entities") from err

    async def upsert(
        self,
        entity: Any,
        conflict_fields: list[str] | None = None,
        update_fields: list[str] | None = None,
    ) -> Any:
        """INSERT … ON CONFLICT DO UPDATE for SQL databases.

        Args:
            entity: Entity to insert or update.
            conflict_fields: Columns forming the unique constraint (defaults to PK).
            update_fields: Columns to update on conflict (defaults to all non-conflict).

        Returns:
            The entity after upsert.

        Raises:
            RepositoryError: On database failure.
            IntegrityError: On constraint violation (propagates typed).
        """
        try:
            data = await self._stamped(
                self._entity_to_dict(entity)  # type: ignore[attr-defined]
            )

            if self.key_field not in data or data.get(self.key_field) is None:  # type: ignore[attr-defined]
                data.pop(self.key_field, None)  # type: ignore[attr-defined]

            conflict_cols = conflict_fields or [self.key_field]  # type: ignore[attr-defined]
            update_cols = update_fields or [k for k in data if k not in conflict_cols]

            columns = list(data.keys())
            safe_columns = [str(Column(c)) for c in columns]
            placeholders = ", ".join("?" for _ in columns)
            params = list(data.values())

            safe_columns_sql = ", ".join(safe_columns)
            if provider_dialect(self.provider) in {"mysql", "mariadb"}:  # type: ignore[attr-defined]
                # MySQL has no ``ON CONFLICT``: the same upsert is spelled
                # ``ON DUPLICATE KEY UPDATE`` and the row being inserted is
                # read back through ``VALUES(col)``. Emitting the Postgres form
                # there is not a syntax variant, it is a hard failure on the
                # first write of the first host that runs MySQL.
                assigned = ", ".join(
                    f"{Column(col)} = VALUES({Column(col)})" for col in update_cols
                )
                query = (
                    f"INSERT INTO {self._table} "  # type: ignore[attr-defined]  # noqa: S608 -- validated Table()/Column() identifiers, values parameterized
                    f"({safe_columns_sql}) VALUES ({placeholders}) "
                    f"ON DUPLICATE KEY UPDATE {assigned}"
                )
            else:
                safe_conflict = ", ".join(str(Column(c)) for c in conflict_cols)
                assigned = ", ".join(
                    f"{Column(col)} = EXCLUDED.{Column(col)}" for col in update_cols
                )
                query = (
                    f"INSERT INTO {self._table} "  # type: ignore[attr-defined]  # noqa: S608 -- validated Table()/Column() identifiers, values parameterized
                    f"({safe_columns_sql}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({safe_conflict}) DO UPDATE SET {assigned}"
                )

            result = await self.provider.execute_query(query, params)  # type: ignore[attr-defined]
            if not result.success:
                _raise_write_failure(result.error_message or "", "Upsert")
            return entity
        except RepositoryError:
            raise
        except IntegrityError:
            # ``upsert`` classifies its failures like ``create`` does; folding
            # them back into the generic branch would erase that.
            raise
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
        ) as err:
            logger.error(
                "repository_upsert_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to upsert entity") from err
