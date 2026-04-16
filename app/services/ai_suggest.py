# ============================================================
# ai_suggest.py — AI-Powered Rule Suggestion Service
# ============================================================
# Instead of manually creating rules one by one, the AI:
# 1. Looks at the table schema (column names, types)
# 2. Samples some actual data from the table
# 3. Analyzes patterns (nulls, ranges, distributions)
# 4. Suggests appropriate DQ rules automatically
#
# The user can then approve or reject each suggestion.
# ============================================================

import json
from groq import Groq
from app.core.config import GROQ_API_KEY, GROQ_MODEL
from app.services.db_connector import DatabaseConnector


class AISuggestService:
    """
    Analyzes a table and suggests data quality rules
    using AI to understand the data patterns.
    """

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL

    def get_table_profile(self, connector: DatabaseConnector, table_name: str) -> dict:
        """
        Build a profile of the table by running several analysis queries.
        
        We gather:
        - Column names and types
        - Row count
        - Null counts per column
        - Min/max for numeric columns
        - Distinct value counts
        - Sample rows
        
        This gives the AI enough context to suggest smart rules.
        """
        profile = {"table_name": table_name, "columns": []}

        # Get columns
        columns = connector.get_columns(table_name)
        if not columns or "error" in columns[0]:
            return {"error": "Could not read table columns"}

        # Get row count
        count_result = connector.execute_query(f"SELECT COUNT(*) FROM {table_name}")
        row_count = count_result["rows"][0][0] if count_result["success"] else 0
        profile["row_count"] = row_count

        # Analyze each column
        for col in columns:
            col_name = col["column_name"]
            col_type = col["data_type"]
            col_info = {
                "name": col_name,
                "type": col_type,
                "nullable": col["is_nullable"]
            }

            # Get null count
            null_result = connector.execute_query(
                f"SELECT COUNT(*) - COUNT({col_name}) AS nulls FROM {table_name}"
            )
            if null_result["success"]:
                null_count = null_result["rows"][0][0]
                col_info["null_count"] = null_count
                col_info["null_pct"] = round(null_count / row_count * 100, 2) if row_count > 0 else 0

            # Get distinct count
            distinct_result = connector.execute_query(
                f"SELECT COUNT(DISTINCT {col_name}) FROM {table_name}"
            )
            if distinct_result["success"]:
                col_info["distinct_count"] = distinct_result["rows"][0][0]

            # For numeric columns, get min/max/avg
            if col_type in ("integer", "numeric", "double precision", "real", "bigint", "smallint"):
                stats_result = connector.execute_query(
                    f"SELECT MIN({col_name}), MAX({col_name}), ROUND(AVG({col_name})::numeric, 2) FROM {table_name}"
                )
                if stats_result["success"]:
                    row = stats_result["rows"][0]
                    col_info["min"] = row[0]
                    col_info["max"] = row[1]
                    col_info["avg"] = row[2]

            # For date columns, get min/max
            if "timestamp" in col_type or "date" in col_type:
                date_result = connector.execute_query(
                    f"SELECT MIN({col_name}), MAX({col_name}) FROM {table_name}"
                )
                if date_result["success"]:
                    row = date_result["rows"][0]
                    col_info["min_date"] = str(row[0])
                    col_info["max_date"] = str(row[1])

            profile["columns"].append(col_info)

        # Get sample rows (5 rows)
        sample_result = connector.execute_query(f"SELECT * FROM {table_name} LIMIT 5")
        if sample_result["success"]:
            profile["sample_columns"] = sample_result["columns"]
            profile["sample_rows"] = sample_result["rows"]

        return profile

    def suggest_rules(self, connector: DatabaseConnector, table_name: str) -> list:
        """
        Use AI to analyze the table profile and suggest DQ rules.
        
        Returns a list of suggested rules like:
        [
            {
                "column_name": "customer_id",
                "check_type": "null_check",
                "max_value": "5",
                "severity": "warning",
                "reason": "22.77% null values detected — may indicate missing customer data"
            },
            ...
        ]
        """
        # Step 1: Profile the table
        profile = self.get_table_profile(connector, table_name)

        if "error" in profile:
            return [{"error": profile["error"]}]

        # Step 2: Ask AI to suggest rules based on the profile
        prompt = f"""You are a data quality expert. Analyze this table profile and suggest 
data quality monitoring rules.

TABLE PROFILE:
{json.dumps(profile, indent=2, default=str)}

Based on this analysis, suggest data quality rules. For each rule, provide:
- column_name: which column to monitor
- check_type: one of "null_check", "range_check", "duplicate_check", "freshness_check"
- min_value: minimum allowed value (for range_check, or null)
- max_value: maximum allowed value (for range_check) or threshold (for null_check = max null %, freshness_check = max hours)
- severity: "critical", "warning", or "info"
- reason: one sentence explaining why this rule is important

RULES FOR SUGGESTIONS:
1. Suggest null_check for columns with some nulls (set threshold slightly above current level)
2. Suggest range_check for numeric columns where negative values seem wrong
3. Suggest duplicate_check for columns that look like IDs or unique identifiers
4. Suggest freshness_check for date/timestamp columns
5. Don't suggest more than 8 rules total — focus on the most important ones
6. Consider the column names to understand business context

Respond ONLY with a valid JSON array. No explanations, no markdown, no code blocks.
Example format:
[
    {{"column_name": "price", "check_type": "range_check", "min_value": "0", "max_value": "50000", "severity": "critical", "reason": "Negative prices detected, likely returns that should be filtered"}}
]"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )

            response_text = response.choices[0].message.content.strip()

            # Clean up response — remove markdown if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse JSON
            suggestions = json.loads(response_text)
            return suggestions

        except json.JSONDecodeError as e:
            return [{"error": f"Failed to parse AI response: {str(e)}", "raw": response_text}]
        except Exception as e:
            return [{"error": f"AI suggestion failed: {str(e)}"}]