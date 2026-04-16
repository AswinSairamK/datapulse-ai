# ============================================================
# dq_engine.py — Data Quality Check Engine
# ============================================================
# This is the core monitoring engine. It connects to the user's
# database, runs each monitoring rule, and calculates health scores.
#
# Five types of checks:
# 1. null_check     — What % of a column is null?
# 2. range_check    — Are values within min/max bounds?
# 3. duplicate_check — Are there unexpected duplicates?
# 4. freshness_check — Is the data recent enough?
# 5. custom_sql     — User's own validation query
#
# Each check returns:
# - passed: True/False
# - actual_value: what we measured
# - expected_value: what the rule says it should be
# - message: human-readable explanation
# - score: 0-100 contribution to health score
# ============================================================

from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import MonitoringRule, CheckResult, DataSource
from app.services.db_connector import DatabaseConnector


class DQEngine:
    """
    Runs data quality checks against a user's database
    based on the monitoring rules they've configured.
    """

    def __init__(self, db_session: Session):
        """
        db_session: SQLAlchemy session for saving check results
                    to DataPulse's own database.
        """
        self.db = db_session

    def _get_connector(self, source: DataSource) -> DatabaseConnector:
        """Create a connector to the user's database."""
        from app.core.security import decrypt_password
        return DatabaseConnector(
            host=source.host,
            port=source.port,
            database=source.database_name,
            username=source.username,
            password=decrypt_password(source.password),
            db_type=source.db_type
        )

    # ============================================================
    # Individual check methods
    # ============================================================

    def run_null_check(self, connector: DatabaseConnector, rule: MonitoringRule) -> dict:
        """
        Check what percentage of a column contains NULL values.

        SQL logic:
        - Count total rows in the table
        - Count rows where the column IS NULL
        - Calculate null percentage

        Example:
        Rule: "orders.customer_id should have < 1% nulls"
        Result: "Found 0.2% null values" → PASS
        """
        # Build and run the SQL query
        query = f"""
            SELECT 
                COUNT(*) AS total_rows,
                COUNT(*) - COUNT({rule.column_name}) AS null_count,
                ROUND(
                    (COUNT(*) - COUNT({rule.column_name}))::numeric / 
                    NULLIF(COUNT(*), 0) * 100, 2
                ) AS null_percentage
            FROM {rule.table_name}
        """
        result = connector.execute_query(query)

        if not result["success"]:
            return {
                "passed": False,
                "actual_value": "Query failed",
                "expected_value": "0% nulls",
                "message": f"Error running null check: {result['error']}",
                "score": 0
            }

        # Extract results from the query
        row = result["rows"][0]
        total_rows = row[0]
        null_count = row[1]
        null_pct = float(row[2]) if row[2] is not None else 0

        # Determine pass/fail
        # If max_value is set, use it as threshold (e.g., "allow up to 5% nulls")
        # Otherwise, any nulls = fail
        threshold = float(rule.max_value) if rule.max_value else 0

        passed = null_pct <= threshold

        # Calculate score (100 = perfect, 0 = terrible)
        # If null_pct is 0, score is 100
        # If null_pct exceeds threshold, score drops proportionally
        if passed:
            score = 100.0
        else:
            # Score decreases as null_pct increases beyond threshold
            score = max(0, 100 - (null_pct - threshold) * 10)

        return {
            "passed": passed,
            "actual_value": f"{null_pct}% nulls ({null_count} of {total_rows} rows)",
            "expected_value": f"<= {threshold}% nulls",
            "message": f"{'PASS' if passed else 'FAIL'}: {null_pct}% null values in {rule.table_name}.{rule.column_name}",
            "score": score
        }

    def run_range_check(self, connector: DatabaseConnector, rule: MonitoringRule) -> dict:
        """
        Check if values in a numeric column fall within expected bounds.

        SQL logic:
        - Find MIN and MAX values in the column
        - Compare against the rule's min_value and max_value

        Example:
        Rule: "orders.price should be between 0 and 50000"
        Result: "Max value is 82340, exceeds 50000" → FAIL
        """
        query = f"""
            SELECT 
                MIN({rule.column_name}) AS min_val,
                MAX({rule.column_name}) AS max_val,
                COUNT(*) AS total_rows,
                COUNT(CASE 
                    WHEN {rule.column_name} < {rule.min_value or 0} 
                    OR {rule.column_name} > {rule.max_value or 999999999} 
                    THEN 1 
                END) AS out_of_range_count
            FROM {rule.table_name}
            WHERE {rule.column_name} IS NOT NULL
        """
        result = connector.execute_query(query)

        if not result["success"]:
            return {
                "passed": False,
                "actual_value": "Query failed",
                "expected_value": f"Between {rule.min_value} and {rule.max_value}",
                "message": f"Error running range check: {result['error']}",
                "score": 0
            }

        row = result["rows"][0]
        min_val = row[0]
        max_val = row[1]
        total_rows = row[2]
        out_of_range = row[3]

        # Check if all values are within bounds
        min_ok = True if rule.min_value is None else float(min_val) >= float(rule.min_value)
        max_ok = True if rule.max_value is None else float(max_val) <= float(rule.max_value)
        passed = min_ok and max_ok

        # Calculate score
        if passed:
            score = 100.0
        else:
            violation_pct = (out_of_range / total_rows * 100) if total_rows > 0 else 100
            score = max(0, 100 - violation_pct * 5)

        return {
            "passed": passed,
            "actual_value": f"min={min_val}, max={max_val}, {out_of_range} out of range",
            "expected_value": f"Between {rule.min_value or 'any'} and {rule.max_value or 'any'}",
            "message": f"{'PASS' if passed else 'FAIL'}: Values range from {min_val} to {max_val} in {rule.table_name}.{rule.column_name}",
            "score": score
        }

    def run_duplicate_check(self, connector: DatabaseConnector, rule: MonitoringRule) -> dict:
        """
        Check if a column has unexpected duplicate values.

        SQL logic:
        - Group by the column and count occurrences
        - Find groups with count > 1 (duplicates)

        Example:
        Rule: "orders.order_id should be unique"
        Result: "Found 14 duplicate values" → FAIL
        """
        query = f"""
            SELECT 
                COUNT(*) AS total_rows,
                COUNT(DISTINCT {rule.column_name}) AS unique_values,
                COUNT(*) - COUNT(DISTINCT {rule.column_name}) AS duplicate_count
            FROM {rule.table_name}
            WHERE {rule.column_name} IS NOT NULL
        """
        result = connector.execute_query(query)

        if not result["success"]:
            return {
                "passed": False,
                "actual_value": "Query failed",
                "expected_value": "0 duplicates",
                "message": f"Error running duplicate check: {result['error']}",
                "score": 0
            }

        row = result["rows"][0]
        total_rows = row[0]
        unique_values = row[1]
        duplicate_count = row[2]

        passed = duplicate_count == 0

        if passed:
            score = 100.0
        else:
            dup_pct = (duplicate_count / total_rows * 100) if total_rows > 0 else 100
            score = max(0, 100 - dup_pct * 2)

        return {
            "passed": passed,
            "actual_value": f"{duplicate_count} duplicates ({unique_values} unique of {total_rows} total)",
            "expected_value": "0 duplicates",
            "message": f"{'PASS' if passed else 'FAIL'}: {duplicate_count} duplicate values in {rule.table_name}.{rule.column_name}",
            "score": score
        }

    def run_freshness_check(self, connector: DatabaseConnector, rule: MonitoringRule) -> dict:
        """
        Check if the data is recent enough.

        SQL logic:
        - Find the MAX (most recent) value in a datetime column
        - Calculate how many hours ago that was
        - Compare against the threshold

        Example:
        Rule: "orders.updated_at should be within 24 hours"
        Result: "Last update was 18 hours ago" → PASS
        """
        query = f"""
            SELECT 
                MAX({rule.column_name}) AS latest_value,
                EXTRACT(EPOCH FROM (NOW() - MAX({rule.column_name}))) / 3600 AS hours_ago
            FROM {rule.table_name}
        """
        result = connector.execute_query(query)

        if not result["success"]:
            return {
                "passed": False,
                "actual_value": "Query failed",
                "expected_value": f"Within {rule.max_value} hours",
                "message": f"Error running freshness check: {result['error']}",
                "score": 0
            }

        row = result["rows"][0]
        latest_value = row[0]
        hours_ago = round(float(row[1]), 1) if row[1] is not None else None

        if hours_ago is None:
            return {
                "passed": False,
                "actual_value": "No data found",
                "expected_value": f"Within {rule.max_value} hours",
                "message": f"FAIL: No data found in {rule.table_name}.{rule.column_name}",
                "score": 0
            }

        threshold_hours = float(rule.max_value) if rule.max_value else 24
        passed = hours_ago <= threshold_hours

        if passed:
            score = 100.0
        else:
            overtime_ratio = hours_ago / threshold_hours
            score = max(0, 100 - (overtime_ratio - 1) * 50)

        return {
            "passed": passed,
            "actual_value": f"Last update {hours_ago} hours ago ({latest_value})",
            "expected_value": f"Within {threshold_hours} hours",
            "message": f"{'PASS' if passed else 'FAIL'}: Data is {hours_ago} hours old in {rule.table_name}.{rule.column_name}",
            "score": score
        }

    def run_custom_sql_check(self, connector: DatabaseConnector, rule: MonitoringRule) -> dict:
        """
        Run a user-defined SQL query as a DQ check.

        The user writes a query that should return 0 rows if
        everything is fine. Any rows returned = problems found.

        Example:
        SQL: "SELECT * FROM orders WHERE status NOT IN ('active', 'completed', 'cancelled')"
        Result: "Found 5 rows with invalid status" → FAIL
        """
        if not rule.custom_sql:
            return {
                "passed": False,
                "actual_value": "No SQL provided",
                "expected_value": "0 violation rows",
                "message": "FAIL: No custom SQL query defined",
                "score": 0
            }

        result = connector.execute_query(rule.custom_sql)

        if not result["success"]:
            return {
                "passed": False,
                "actual_value": "Query failed",
                "expected_value": "0 violation rows",
                "message": f"Error running custom SQL: {result['error']}",
                "score": 0
            }

        violation_count = result["row_count"]
        passed = violation_count == 0

        if passed:
            score = 100.0
        else:
            score = max(0, 100 - violation_count * 5)

        return {
            "passed": passed,
            "actual_value": f"{violation_count} violation rows found",
            "expected_value": "0 violation rows",
            "message": f"{'PASS' if passed else 'FAIL'}: Custom SQL found {violation_count} violations",
            "score": score
        }

    # ============================================================
    # Main execution method
    # ============================================================

    def run_checks_for_source(self, source_id: int,  user_id: int = None) -> dict:
        """
        Run ALL active monitoring rules for a given data source.
        Validates table/column names against schema before running queries.
        """
        from app.core.validators import validate_table_name, validate_column_name

        # Step 1: Load data source
        source = self.db.query(DataSource).filter(DataSource.id == source_id).first()
        if not source:
            return {"error": "Data source not found"}

        # Step 2: Load active rules
        rules = self.db.query(MonitoringRule).filter(
            MonitoringRule.data_source_id == source_id,
            MonitoringRule.is_active == True
        ).all()

        if not rules:
            return {
                "data_source": source.name,
                "message": "No active rules configured",
                "total_rules": 0,
                "results": []
            }

        # Step 3: Connect to user's database
        connector = self._get_connector(source)
        success, msg = connector.test_connection()
        if not success:
            return {"error": f"Cannot connect to database: {msg}"}

        # Step 4: Run each rule
        results = []
        check_map = {
            "null_check": self.run_null_check,
            "range_check": self.run_range_check,
            "duplicate_check": self.run_duplicate_check,
            "freshness_check": self.run_freshness_check,
            "custom_sql": self.run_custom_sql_check,
        }

        for rule in rules:
            # VALIDATE table and column names against actual schema
            # This prevents SQL injection via malicious rule names
            if not validate_table_name(connector, rule.table_name):
                result = {
                    "passed": False,
                    "actual_value": "Invalid table name",
                    "expected_value": "N/A",
                    "message": f"SECURITY: Table '{rule.table_name}' does not exist or is invalid",
                    "score": 0
                }
            elif rule.column_name and not validate_column_name(connector, rule.table_name, rule.column_name):
                result = {
                    "passed": False,
                    "actual_value": "Invalid column name",
                    "expected_value": "N/A",
                    "message": f"SECURITY: Column '{rule.column_name}' does not exist in table '{rule.table_name}'",
                    "score": 0
                }
            else:
                # Find the right check method for this rule type
                check_fn = check_map.get(rule.check_type)

                if not check_fn:
                    result = {
                        "passed": False,
                        "actual_value": "Unknown check type",
                        "expected_value": "N/A",
                        "message": f"Unknown check type: {rule.check_type}",
                        "score": 0
                    }
                else:
                    result = check_fn(connector, rule)

            # Save the result to DataPulse's database
            check_result = CheckResult(
                user_id=user_id,
                data_source_id=source_id,
                rule_id=rule.id,
                table_name=rule.table_name,
                column_name=rule.column_name,
                check_type=rule.check_type,
                passed=result["passed"],
                actual_value=result["actual_value"],
                expected_value=result["expected_value"],
                message=result["message"],
                score=result["score"],
            )
            self.db.add(check_result)

            results.append({
                "rule_id": rule.id,
                "table": rule.table_name,
                "column": rule.column_name,
                "check_type": rule.check_type,
                "severity": rule.severity,
                **result
            })

        self.db.commit()

        total_score = sum(r["score"] for r in results)
        avg_score = round(total_score / len(results), 1) if results else 100

        passed_count = sum(1 for r in results if r["passed"])
        failed_count = len(results) - passed_count

        return {
            "data_source": source.name,
            "overall_score": avg_score,
            "total_rules": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "results": results
        }