# ============================================================
# db_connector.py — Database connection abstractions
# ============================================================
# Defines a base connector interface and concrete implementations
# for PostgreSQL and MySQL.
#
# All connectors implement the same methods so the rest of the
# system (DQ engine, AI chat, masking) works the same regardless
# of the database type.
# ============================================================

import psycopg2
import pymysql
from typing import Optional


class BaseConnector:
    """
    Base class defining the connector interface.
    Subclasses implement database-specific logic.
    """
    
    def __init__(self, host: str, port: str, database: str, username: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
    
    def test_connection(self) -> tuple[bool, str]:
        raise NotImplementedError
    
    def get_tables(self) -> list[dict]:
        raise NotImplementedError
    
    def get_columns(self, table_name: str) -> list[dict]:
        raise NotImplementedError
    
    def execute_query(self, query: str, params: tuple = None) -> dict:
        raise NotImplementedError


class PostgreSQLConnector(BaseConnector):
    """
    Connector for PostgreSQL databases.
    Uses psycopg2 driver.
    """

    def _get_connection(self):
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.username,
            password=self.password,
            connect_timeout=10
        )

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            return True, "Connected successfully"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def get_tables(self) -> list[dict]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = []

            for row in cur.fetchall():
                table_name = row[0]
                cur.execute(f"""
                    SELECT n_live_tup 
                    FROM pg_stat_user_tables 
                    WHERE relname = '{table_name}'
                """)
                count_row = cur.fetchone()
                row_count = count_row[0] if count_row else 0

                tables.append({
                    "table_name": table_name,
                    "row_count": row_count
                })

            cur.close()
            conn.close()
            return tables
        except Exception as e:
            return [{"error": str(e)}]

    def get_columns(self, table_name: str) -> list[dict]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))

            columns = []
            for row in cur.fetchall():
                columns.append({
                    "column_name": row[0],
                    "data_type": row[1],
                    "is_nullable": row[2]
                })

            cur.close()
            conn.close()
            return columns
        except Exception as e:
            return [{"error": str(e)}]

    def execute_query(self, query: str, params: tuple = None) -> dict:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute(query, params)

            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                rows = [list(row) for row in rows]

                result = {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
            else:
                result = {
                    "success": True,
                    "columns": [],
                    "rows": [],
                    "row_count": 0
                }

            cur.close()
            conn.close()
            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class MySQLConnector(BaseConnector):
    """
    Connector for MySQL/MariaDB databases.
    Uses pymysql driver.
    """

    def _get_connection(self):
        return pymysql.connect(
            host=self.host,
            port=int(self.port),
            database=self.database,
            user=self.username,
            password=self.password,
            connect_timeout=10,
            charset='utf8mb4'
        )

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            return True, "Connected successfully"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def get_tables(self) -> list[dict]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            # MySQL uses TABLE_ROWS in information_schema
            cur.execute("""
                SELECT TABLE_NAME, TABLE_ROWS
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """, (self.database,))

            tables = []
            for row in cur.fetchall():
                tables.append({
                    "table_name": row[0],
                    "row_count": row[1] if row[1] else 0
                })

            cur.close()
            conn.close()
            return tables
        except Exception as e:
            return [{"error": str(e)}]

    def get_columns(self, table_name: str) -> list[dict]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (self.database, table_name))

            columns = []
            for row in cur.fetchall():
                columns.append({
                    "column_name": row[0],
                    "data_type": row[1],
                    "is_nullable": row[2]
                })

            cur.close()
            conn.close()
            return columns
        except Exception as e:
            return [{"error": str(e)}]

    def execute_query(self, query: str, params: tuple = None) -> dict:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute(query, params)

            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                rows = [list(row) for row in rows]

                result = {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
            else:
                result = {
                    "success": True,
                    "columns": [],
                    "rows": [],
                    "row_count": 0
                }

            cur.close()
            conn.close()
            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

class SnowflakeConnector(BaseConnector):
    """
    Connector for Snowflake cloud data warehouse.
    
    Snowflake uses a different connection model than PostgreSQL/MySQL:
    - Account identifier instead of host/port
    - Warehouse for compute resources
    - Schema is required for queries
    """

    def __init__(self, host: str, port: str, database: str, username: str, password: str):
        """
        For Snowflake, we repurpose the standard fields:
        - host: account identifier (e.g., "mgccivg-hj52143")
        - port: warehouse name (e.g., "COMPUTE_WH")
        - database: database.schema (e.g., "SNOWFLAKE_SAMPLE_DATA.TPCH_SF1")
        """
        self.account = host
        self.warehouse = port
        # Split database.schema if provided
        if "." in database:
            self.database, self.schema = database.split(".", 1)
        else:
            self.database = database
            self.schema = "PUBLIC"
        self.username = username
        self.password = password

    def _get_connection(self):
        import snowflake.connector
        return snowflake.connector.connect(
            account=self.account,
            user=self.username,
            password=self.password,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema,
            login_timeout=30
        )

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            return True, "Connected successfully"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def get_tables(self) -> list[dict]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            # Snowflake uses INFORMATION_SCHEMA like PostgreSQL but with uppercase
            cur.execute(f"""
                SELECT TABLE_NAME, ROW_COUNT
                FROM {self.database}.INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = '{self.schema}'
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)

            tables = []
            for row in cur.fetchall():
                tables.append({
                    "table_name": row[0],
                    "row_count": row[1] if row[1] else 0
                })

            cur.close()
            conn.close()
            return tables
        except Exception as e:
            return [{"error": str(e)}]

    def get_columns(self, table_name: str) -> list[dict]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute(f"""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM {self.database}.INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{self.schema}'
                AND TABLE_NAME = '{table_name.upper()}'
                ORDER BY ORDINAL_POSITION
            """)

            columns = []
            for row in cur.fetchall():
                columns.append({
                    "column_name": row[0],
                    "data_type": row[1],
                    "is_nullable": row[2]
                })

            cur.close()
            conn.close()
            return columns
        except Exception as e:
            return [{"error": str(e)}]

    def execute_query(self, query: str, params: tuple = None) -> dict:
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)

            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                rows = [list(row) for row in rows]

                result = {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
            else:
                result = {
                    "success": True,
                    "columns": [],
                    "rows": [],
                    "row_count": 0
                }

            cur.close()
            conn.close()
            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# Factory function to create the right connector based on database type
def DatabaseConnector(host, port, database, username, password, db_type="postgresql"):
    """
    Factory function — creates the right connector based on db_type.
    
    Args:
        db_type: "postgresql", "mysql", or "snowflake"
    """
    if db_type == "mysql":
        return MySQLConnector(host, port, database, username, password)
    elif db_type == "snowflake":
        return SnowflakeConnector(host, port, database, username, password)
    else:
        return PostgreSQLConnector(host, port, database, username, password)