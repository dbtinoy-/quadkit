"""Write mixin for SQLRepository: create, update, soft_delete, delete_by_id, upsert."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from quadkit.contracts.data.identifiers import Column
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DuplicateKeyError,
    ForeignKeyError,
    QueryError,
    RepositoryError,
    TenantScopingError,
)

logger = get_logger(__name__)


class _WriteMixin:
    """Provides ``create``, ``update``, ``soft_delete``, ``delete_by_id``, ``upsert__."""

    async def create(self, entity: Any) -> Any:
        """Insert *entity* into the database.

        Args:
            entity: Entity to insert.

        Returns:
            The entity with the generated primary key set.

        Raises:
            RepositoryError: On database failure or constraint violation.
        """
        try:
            data = self._entity_to_dict(entity)  # type: ignore[attr-defined]

            now = ambient_clock.now()
            if "created_at" not in data:
                data["created_at"] = now
            if "updated_at" not in data:
                data["updated_at"] = now

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
                raise RepositoryError(result.error_message or "Insert failed")
            if result.success and result.inserted_id:
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
            # RepositoryError subclasses DatabaseError — re-raise the
            # specific error (e.g. "Insert failed: <db detail>") instead of
            # re-wrapping it into the generic message below.
            raise
        except (
            DatabaseError,
            QueryError,
            DuplicateKeyError,
            ForeignKeyError,
            DatabaseConnectionError,
        ) as err:
            logger.exception(
                "Failed create table=%s entity=%s",
                self.table_name,  # type: ignore[attr-defined]
                entity,
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

        now = ambient_clock.now()
        data["updated_at"] = now

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
                raise RepositoryError(f"Update failed: {result.error_message}")

            for hook in getattr(self, "_post_save_hooks", []):
                await hook(entity)
            return entity
        except RepositoryError:
            raise
        except (DatabaseError, QueryError, DatabaseConnectionError) as err:
            logger.exception(
                "Failed update table=%s entity=%s",
                self.table_name,  # type: ignore[attr-defined]
                entity,
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

        now = ambient_clock.now()
        data["updated_at"] = now

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
        except RepositoryError:
            raise
        except (DatabaseError, QueryError, DatabaseConnectionError) as err:
            logger.exception(
                "Failed versioned update table=%s entity=%s",
                self.table_name,  # type: ignore[attr-defined]
                entity,
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
        except (
            DatabaseError,
            QueryError,
            ForeignKeyError,
            DatabaseConnectionError,
        ) as err:
            logger.exception("Failed soft_delete table=%s key=%s", self.table_name, key)  # type: ignore[attr-defined]
            raise RepositoryError(f"Failed to soft delete entity {key}") from err

    async def delete_by_id(self, key: Any) -> bool:
        """Delete entity by primary key.

        Args:
            key: Primary key of the entity to delete.

        Returns:
            ``True`` if an entity was deleted.

        Raises:
            RepositoryError: On database failure.
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
        except RepositoryError:
            raise
        except (
            DatabaseError,
            QueryError,
            ForeignKeyError,
            DatabaseConnectionError,
        ) as err:
            logger.exception(
                "Failed delete_by_id table=%s key=%s",
                self.table_name,  # type: ignore[attr-defined]
                key,
            )
            raise RepositoryError("Failed to delete entity") from err

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
        """
        try:
            data = self._entity_to_dict(entity)  # type: ignore[attr-defined]
            now = ambient_clock.now()
            if "created_at" not in data:
                data["created_at"] = now
            if "updated_at" not in data:
                data["updated_at"] = now

            if self.key_field not in data or data.get(self.key_field) is None:  # type: ignore[attr-defined]
                data.pop(self.key_field, None)  # type: ignore[attr-defined]

            conflict_cols = conflict_fields or [self.key_field]  # type: ignore[attr-defined]
            update_cols = update_fields or [k for k in data if k not in conflict_cols]

            columns = list(data.keys())
            safe_columns = [str(Column(c)) for c in columns]
            placeholders = ", ".join("?" for _ in columns)
            params = list(data.values())

            safe_conflict = ", ".join(str(Column(c)) for c in conflict_cols)
            safe_set = ", ".join(
                f"{Column(col)} = EXCLUDED.{Column(col)}" for col in update_cols
            )

            query = (
                f"INSERT INTO {self._table} "  # type: ignore[attr-defined]  # noqa: S608 -- validated Table()/Column() identifiers, values parameterized
                f"({', '.join(safe_columns)}) VALUES ({placeholders}) "
                f"ON CONFLICT ({safe_conflict}) DO UPDATE SET {safe_set}"
            )

            result = await self.provider.execute_query(query, params)  # type: ignore[attr-defined]
            if not result.success:
                raise RepositoryError(
                    f"Upsert failed: {result.error_message}",
                )
            return entity
        except RepositoryError:
            raise
        except (
            DatabaseError,
            QueryError,
            DuplicateKeyError,
            DatabaseConnectionError,
        ) as err:
            logger.exception(
                "Failed upsert table=%s",
                self.table_name,  # type: ignore[attr-defined]
            )
            raise RepositoryError("Failed to upsert entity") from err
