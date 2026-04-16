# ============================================================
# validators.py — SQL injection prevention
# ============================================================
# Since we can't use parameterized queries for table/column names
# (PostgreSQL doesn't allow it), we validate them against the
# actual database schema before using them in SQL.
#
# If a table/column name doesn't exist in the real database,
# we reject it — preventing SQL injection attacks.
# ============================================================

import re
from app.services.db_connector import DatabaseConnector


# Allowed characters in identifiers: letters, digits, underscore
# This is the first line of defense — reject anything weird
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def is_safe_identifier(name: str) -> bool:
    """
    Check if a string is a valid SQL identifier.
    
    Valid: "orders", "customer_id", "table1"
    Invalid: "orders; DROP TABLE", "1table", "users--", "tab'le"
    """
    if not name or not isinstance(name, str):
        return False
    
    # Must match the pattern (only letters, digits, underscore)
    if not IDENTIFIER_PATTERN.match(name):
        return False
    
    # Length check — reasonable limit
    if len(name) > 63:  # PostgreSQL max identifier length
        return False
    
    return True


def validate_table_name(connector: DatabaseConnector, table_name: str) -> bool:
    """
    Verify that a table name:
    1. Is a safe identifier (no SQL injection characters)
    2. Actually exists in the database
    
    This is the strong validation — even if someone sneaks
    past the regex check, the table must actually exist.
    """
    # First: basic safety check
    if not is_safe_identifier(table_name):
        return False
    
    # Second: verify it exists in the database
    tables = connector.get_tables()
    existing_names = [t.get("table_name") for t in tables if "error" not in t]
    
    return table_name in existing_names


def validate_column_name(connector: DatabaseConnector, table_name: str, column_name: str) -> bool:
    """
    Verify that a column name:
    1. Is a safe identifier
    2. Actually exists in the specified table
    
    Note: assumes table_name is already validated.
    """
    if not column_name:
        return True  # Column is optional for some rules
    
    if not is_safe_identifier(column_name):
        return False
    
    columns = connector.get_columns(table_name)
    existing_names = [c.get("column_name") for c in columns if "error" not in c]
    
    return column_name in existing_names


def validate_numeric(value: str) -> bool:
    """
    Validate that a value is a safe numeric string.
    Used for min_value/max_value in range checks.
    
    Valid: "0", "100", "-50.5", "1e10"
    Invalid: "0; DROP TABLE", "abc", "null"
    """
    if not value:
        return True  # Optional
    
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

import sqlparse


# Dangerous SQL keywords that should never appear in AI-generated queries
# These can modify or destroy data
DANGEROUS_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXECUTE", "EXEC", "MERGE",
    "REPLACE", "RENAME", "COMMENT", "LOCK", "CALL", "DO",
    "COPY", "VACUUM", "REINDEX", "CLUSTER", "ANALYZE", "SET",
    "DECLARE", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT",
}


def is_safe_select_query(sql: str) -> tuple[bool, str]:
    """
    Validate that a SQL query is a safe SELECT statement.
    
    Checks:
    1. The query parses successfully
    2. The statement type is SELECT (not DML/DDL)
    3. No dangerous keywords appear anywhere
    4. Only one statement (no stacked queries with semicolons)
    
    Returns:
        (True, "safe") — if the query is a safe SELECT
        (False, "reason") — if it's dangerous, with explanation
    """
    if not sql or not isinstance(sql, str):
        return False, "Empty query"
    
    # Parse the SQL
    try:
        parsed = sqlparse.parse(sql)
    except Exception as e:
        return False, f"Could not parse SQL: {str(e)}"
    
    # Must have exactly one statement (no stacked queries)
    if len(parsed) == 0:
        return False, "No SQL statement found"
    
    if len(parsed) > 1:
        # Check if extras are just empty/whitespace
        non_empty = [s for s in parsed if str(s).strip()]
        if len(non_empty) > 1:
            return False, "Multiple statements not allowed (possible SQL injection)"
    
    statement = parsed[0]
    
    # Get the statement type (SELECT, INSERT, UPDATE, etc.)
    stmt_type = statement.get_type()
    
    if stmt_type != "SELECT":
        return False, f"Only SELECT queries allowed, got: {stmt_type}"
    
    # Check for dangerous keywords in the raw SQL (case-insensitive)
    # This catches cases where keywords are used as column/table names
    # in a way the parser might miss
    sql_upper = sql.upper()
    
    # Use word boundaries to avoid false positives
    # For example, "updated_at" contains "UPDATE" but is fine
    import re
    for keyword in DANGEROUS_KEYWORDS:
        # Match the keyword as a whole word only
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            return False, f"Dangerous keyword detected: {keyword}"
    
    return True, "safe"