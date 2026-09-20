"""Database backend implementations.

One class per engine: URL parsing, the client binary, the shell hand-off and
the backup/restore commands. The registry and the connection manager in
:mod:`quadkit.cli.registry.database` drive these through the
:class:`~quadkit.cli.registry.backend_base.DatabaseBackend` contract.
"""

from __future__ import annotations

import re
import shutil
from typing import TYPE_CHECKING, Any

from quadkit.cli.registry.backend_base import (
    DatabaseBackend as DatabaseBackend,
)

if TYPE_CHECKING:
    from quadkit.contracts.data.sql.database import DatabaseProviderProtocol


class SQLiteBackend(DatabaseBackend):
    """SQLite database backend."""

    name = "sqlite"
    aliases = []

    def parse_url(self, url: str) -> dict[str, Any]:
        path = url.replace("sqlite:///", "")
        return {"backend": "sqlite", "path": path}

    def get_client_binary(self) -> str | None:
        return shutil.which("sqlite3")

    def build_shell_command(self, params: dict[str, Any]) -> list[str]:
        binary = self.get_client_binary()
        if not binary:
            raise RuntimeError("sqlite3 client not found")
        db_path = params.get("path", "dev.db")
        return [binary, db_path]

    async def get_tables(self, provider: DatabaseProviderProtocol) -> list[str]:
        result = await provider.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        )
        return [row["name"] for row in result.rows]

    async def get_columns(
        self, provider: DatabaseProviderProtocol, table: str
    ) -> list[dict[str, Any]]:
        result = await provider.execute_query(f"PRAGMA table_info({table})")
        return [
            {
                "name": row.get("name", ""),
                "type": row.get("type", ""),
                "nullable": not row.get("notnull", False),
                "default": row.get("dflt_value"),
                "primary_key": bool(row.get("pk", 0)),
            }
            for row in result.rows
        ]

    def build_backup_command(
        self,
        params: dict[str, Any],
        output_path: str,
    ) -> list[str]:
        """Build SQLite backup command."""
        binary = self.get_client_binary()
        if not binary:
            raise RuntimeError("sqlite3 client not found")
        db_path = params.get("path", "dev.db")
        return [binary, db_path, f".output {output_path}", ".dump"]

    def build_restore_command(
        self,
        params: dict[str, Any],
        input_path: str,
    ) -> list[str]:
        """Build SQLite restore command."""
        binary = self.get_client_binary()
        if not binary:
            raise RuntimeError("sqlite3 client not found")
        db_path = params.get("path", "dev.db")
        return [binary, db_path]


class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL database backend."""

    name = "postgresql"
    aliases = ["postgres", "pg"]

    URL_PATTERN = re.compile(
        r"^(?P<backend>\w+)://(?:(?P<user>[^:@]+)(?::(?P<password>[^@]+))?@)?"
        r"(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<database>.*)$",
    )

    def parse_url(self, url: str) -> dict[str, Any]:
        match = self.URL_PATTERN.match(url)
        if not match:
            return {"backend": "postgresql", "error": "Invalid URL format"}
        return {
            "backend": "postgresql",
            "user": match.group("user"),
            "password": match.group("password"),
            "host": match.group("host"),
            "port": match.group("port") or "5432",
            "database": match.group("database"),
        }

    def get_client_binary(self) -> str | None:
        return shutil.which("psql")

    def build_shell_command(self, params: dict[str, Any]) -> list[str]:
        binary = self.get_client_binary()
        if not binary:
            raise RuntimeError("psql client not found")

        cmd = [binary]
        if params.get("user"):
            cmd.extend(["-U", params["user"]])
        if params.get("host"):
            cmd.extend(["-h", params["host"]])
        if params.get("port"):
            cmd.extend(["-p", params["port"]])
        cmd.append(params.get("database", "postgres"))
        return cmd

    async def get_tables(self, provider: DatabaseProviderProtocol) -> list[str]:
        result = await provider.execute_query("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        return [row["table_name"] for row in result.rows]

    async def get_columns(
        self, provider: DatabaseProviderProtocol, table: str
    ) -> list[dict[str, Any]]:
        result = await provider.execute_query(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
        """,
            [table],
        )
        return [
            {
                "name": row["column_name"],
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
                "default": row["column_default"],
                "primary_key": False,
            }
            for row in result.rows
        ]

    def build_backup_command(
        self,
        params: dict[str, Any],
        output_path: str,
    ) -> list[str]:
        """Build PostgreSQL backup command."""
        binary = shutil.which("pg_dump")
        if not binary:
            raise RuntimeError("pg_dump client not found")
        cmd = ["pg_dump"]
        if params.get("user"):
            cmd.extend(["-U", params["user"]])
        if params.get("host"):
            cmd.extend(["-h", params["host"]])
        if params.get("port"):
            cmd.extend(["-p", params["port"]])
        cmd.extend(["-f", output_path, params.get("database", "postgres")])
        return cmd

    def build_restore_command(
        self,
        params: dict[str, Any],
        input_path: str,
    ) -> list[str]:
        """Build PostgreSQL restore command."""
        binary = shutil.which("psql")
        if not binary:
            raise RuntimeError("psql client not found")
        cmd = ["psql"]
        if params.get("user"):
            cmd.extend(["-U", params["user"]])
        if params.get("host"):
            cmd.extend(["-h", params["host"]])
        if params.get("port"):
            cmd.extend(["-p", params["port"]])
        cmd.extend(["-d", params.get("database", "postgres"), "-f", input_path])
        return cmd


class MySQLBackend(DatabaseBackend):
    """MySQL database backend."""

    name = "mysql"
    aliases = []

    URL_PATTERN = re.compile(
        r"^(?P<backend>\w+)://(?:(?P<user>[^:@]+)(?::(?P<password>[^@]+))?@)?"
        r"(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<database>.*)$",
    )

    def parse_url(self, url: str) -> dict[str, Any]:
        match = self.URL_PATTERN.match(url)
        if not match:
            return {"backend": "mysql", "error": "Invalid URL format"}
        return {
            "backend": "mysql",
            "user": match.group("user"),
            "password": match.group("password"),
            "host": match.group("host"),
            "port": match.group("port") or "3306",
            "database": match.group("database"),
        }

    def get_client_binary(self) -> str | None:
        return shutil.which("mysql")

    def subprocess_env(self, params: dict[str, Any]) -> dict[str, str]:
        """Pass the MySQL password via ``MYSQL_PWD`` instead of argv.

        ``-p<password>`` is visible to every local user through ``ps``;
        the environment of the child process is only readable by the
        same user.
        """
        env = super().subprocess_env(params)
        if params.get("password"):
            env["MYSQL_PWD"] = str(params["password"])
        return env

    def build_shell_command(self, params: dict[str, Any]) -> list[str]:
        binary = self.get_client_binary()
        if not binary:
            raise RuntimeError("mysql client not found")

        cmd = [binary]
        if params.get("user"):
            cmd.extend(["-u", params["user"]])
        if params.get("host"):
            cmd.extend(["-h", params["host"]])
        if params.get("port"):
            cmd.extend(["-P", params["port"]])
        cmd.append(params.get("database", "mysql"))
        return cmd

    async def get_tables(self, provider: DatabaseProviderProtocol) -> list[str]:
        result = await provider.execute_query("SHOW TABLES")
        if result.rows:
            key = next(iter(result.rows[0].keys()))
            return [row[key] for row in result.rows]
        return []

    async def get_columns(
        self, provider: DatabaseProviderProtocol, table: str
    ) -> list[dict[str, Any]]:
        result = await provider.execute_query(f"DESCRIBE `{table}`")
        return [
            {
                "name": row.get("Field", ""),
                "type": row.get("Type", ""),
                "nullable": row.get("Null", "") == "YES",
                "default": row.get("Default"),
                "primary_key": row.get("Key", "") == "PRI",
            }
            for row in result.rows
        ]

    def build_backup_command(
        self,
        params: dict[str, Any],
        output_path: str,
    ) -> list[str]:
        """Build MySQL backup command."""
        binary = shutil.which("mysqldump")
        if not binary:
            raise RuntimeError("mysqldump client not found")
        cmd = ["mysqldump"]
        if params.get("user"):
            cmd.extend(["-u", params["user"]])
        if params.get("host"):
            cmd.extend(["-h", params["host"]])
        # --result-file avoids shell redirection for the output
        cmd.extend(["--result-file=" + output_path])
        cmd.append(params.get("database", "mysql"))
        return cmd

    def build_restore_command(
        self,
        params: dict[str, Any],
        input_path: str,
    ) -> list[str]:
        """Build MySQL restore command.

        The backup file is piped to the mysql client via stdin by the
        caller; shell redirection is never used.
        """
        binary = shutil.which("mysql")
        if not binary:
            raise RuntimeError("mysql client not found")
        cmd = ["mysql"]
        if params.get("user"):
            cmd.extend(["-u", params["user"]])
        if params.get("host"):
            cmd.extend(["-h", params["host"]])
        cmd.append(params.get("database", "mysql"))
        return cmd
