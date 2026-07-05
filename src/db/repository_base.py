# =========================================================
# ApexDeploy - Abstract Base Repository
# Provides reusable CRUD primitives for all domain entities
# =========================================================

import json
import logging
from abc import ABC
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.db.database import get_db_connection
from src.core.exceptions import DatabaseException, ResourceNotFoundException

logger = logging.getLogger("db.repository")


class BaseRepository(ABC):
    """Abstract base class encapsulating common async SQLite CRUD operations.

    Each concrete repository sets ``table_name`` and ``id_column`` and
    inherits insert / get / list / update / delete helpers that open
    their own connection via ``get_db_connection()``.
    """

    table_name: str = ""
    id_column: str = "id"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """Safely convert an aiosqlite.Row to a plain dictionary."""
        if row is None:
            return {}
        return dict(row)

    @staticmethod
    def _rows_to_list(rows) -> List[Dict[str, Any]]:
        """Convert a sequence of aiosqlite.Row objects to a list of dicts."""
        return [dict(r) for r in rows]

    @staticmethod
    def _serialize_json(value: Any) -> Optional[str]:
        """Serialize a Python object to a JSON string, or None."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value)

    @staticmethod
    def _deserialize_json(raw: Optional[str]) -> Any:
        """Deserialize a JSON string back to a Python object."""
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    async def insert(
        self,
        columns: Sequence[str],
        values: Sequence[Any],
    ) -> None:
        """Insert a single row into the table.

        Args:
            columns: Column names to populate.
            values: Corresponding values (same order as columns).
        """
        placeholders = ", ".join("?" for _ in columns)
        col_names = ", ".join(columns)
        sql = f"INSERT INTO {self.table_name} ({col_names}) VALUES ({placeholders})"

        try:
            async with get_db_connection() as conn:
                await conn.execute(sql, tuple(values))
                await conn.commit()
        except Exception as e:
            logger.error(f"Insert into {self.table_name} failed: {e}", exc_info=True)
            raise DatabaseException(f"Failed to insert into {self.table_name}: {e}") from e

    async def get_by_id(self, record_id: str) -> Dict[str, Any]:
        """Fetch a single row by its primary key.

        Raises:
            ResourceNotFoundException: If no matching row exists.
        """
        sql = f"SELECT * FROM {self.table_name} WHERE {self.id_column} = ?"

        try:
            async with get_db_connection() as conn:
                async with conn.execute(sql, (record_id,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        raise ResourceNotFoundException(
                            f"{self.table_name} record '{record_id}' not found."
                        )
                    return self._row_to_dict(row)
        except ResourceNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Get by id from {self.table_name} failed: {e}", exc_info=True)
            raise DatabaseException(f"Failed to get from {self.table_name}: {e}") from e

    async def list_all(
        self,
        order_by: str = "rowid DESC",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List all rows with optional ordering and limit."""
        sql = f"SELECT * FROM {self.table_name} ORDER BY {order_by}"
        params: Tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)

        try:
            async with get_db_connection() as conn:
                async with conn.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()
                    return self._rows_to_list(rows)
        except Exception as e:
            logger.error(f"List all from {self.table_name} failed: {e}", exc_info=True)
            raise DatabaseException(f"Failed to list {self.table_name}: {e}") from e

    async def update(
        self,
        record_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """Update specific columns of a row identified by primary key.

        Args:
            record_id: The primary key value.
            updates: Mapping of column -> new value.
        """
        if not updates:
            return

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [record_id]
        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.id_column} = ?"

        try:
            async with get_db_connection() as conn:
                await conn.execute(sql, tuple(values))
                await conn.commit()
        except Exception as e:
            logger.error(f"Update {self.table_name} failed: {e}", exc_info=True)
            raise DatabaseException(f"Failed to update {self.table_name}: {e}") from e

    async def delete(self, record_id: str) -> None:
        """Delete a single row by primary key."""
        sql = f"DELETE FROM {self.table_name} WHERE {self.id_column} = ?"

        try:
            async with get_db_connection() as conn:
                await conn.execute(sql, (record_id,))
                await conn.commit()
        except Exception as e:
            logger.error(f"Delete from {self.table_name} failed: {e}", exc_info=True)
            raise DatabaseException(f"Failed to delete from {self.table_name}: {e}") from e

    async def count(self, where: Optional[str] = None, params: Tuple = ()) -> int:
        """Return the row count, optionally filtered by a WHERE clause."""
        sql = f"SELECT COUNT(*) as cnt FROM {self.table_name}"
        if where:
            sql += f" WHERE {where}"

        try:
            async with get_db_connection() as conn:
                async with conn.execute(sql, params) as cursor:
                    row = await cursor.fetchone()
                    return row["cnt"] if row else 0
        except Exception as e:
            logger.error(f"Count on {self.table_name} failed: {e}", exc_info=True)
            raise DatabaseException(f"Failed to count {self.table_name}: {e}") from e

    async def query(
        self,
        where: str,
        params: Tuple = (),
        order_by: str = "rowid DESC",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Run a filtered SELECT with a custom WHERE clause."""
        sql = f"SELECT * FROM {self.table_name} WHERE {where} ORDER BY {order_by}"
        full_params = list(params)
        if limit is not None:
            sql += " LIMIT ?"
            full_params.append(limit)

        try:
            async with get_db_connection() as conn:
                async with conn.execute(sql, tuple(full_params)) as cursor:
                    rows = await cursor.fetchall()
                    return self._rows_to_list(rows)
        except Exception as e:
            logger.error(f"Query on {self.table_name} failed: {e}", exc_info=True)
            raise DatabaseException(f"Failed to query {self.table_name}: {e}") from e
