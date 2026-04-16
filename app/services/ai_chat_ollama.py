# ============================================================
# ai_chat_ollama.py — Local LLM chat service using Ollama
# ============================================================
# Same interface as ai_chat.py (Groq) but uses a local LLM
# running on the user's machine. Data never leaves the machine.
# ============================================================

import ollama
import json
from app.core.config import OLLAMA_MODEL, OLLAMA_HOST
from app.services.db_connector import BaseConnector


class OllamaChatService:
    """
    Chat service using Ollama (local LLM).
    Same interface as AIChatService (Groq version) for easy swapping.
    """

    def __init__(self):
        self.client = ollama.Client(host=OLLAMA_HOST)
        self.model = OLLAMA_MODEL

    def get_schema_description(self, connector: BaseConnector) -> str:
        """Build a text description of all tables and columns."""
        tables = connector.get_tables()
        schema_text = ""

        for table_info in tables:
            if "error" in table_info:
                continue

            table_name = table_info["table_name"]
            row_count = table_info.get("row_count", "unknown")
            columns = connector.get_columns(table_name)

            schema_text += f"\nTable: {table_name} (approximately {row_count} rows)\n"

            for col in columns:
                if "error" not in col:
                    nullable = "nullable" if col["is_nullable"] == "YES" else "not null"
                    schema_text += f"  - {col['column_name']} ({col['data_type']}, {nullable})\n"

        return schema_text

    def generate_sql(self, question: str, schema: str) -> str:
        """Use Ollama to generate SQL from a natural language question."""
        prompt = f"""You are a PostgreSQL SQL expert. Given the following database schema, write a SQL query to answer the user's question.

DATABASE SCHEMA:
{schema}

RULES:
1. Return ONLY the SQL query, nothing else. No explanations, no markdown, no code blocks.
2. Use only SELECT statements. Never use INSERT, UPDATE, DELETE, DROP, or ALTER.
3. Use proper PostgreSQL syntax.
4. Always use table and column names exactly as shown in the schema.
5. If the question asks about revenue or sales amount, calculate it as (quantity * price).
6. Limit results to 50 rows maximum unless the user asks for more.
7. Use meaningful column aliases with AS for calculated fields.

USER QUESTION: {question}

SQL QUERY:"""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0}
            )

            sql = response["message"]["content"].strip()

            # Clean up markdown if present
            if sql.startswith("```sql"):
                sql = sql[6:]
            if sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()

            return sql

        except Exception as e:
            return f"ERROR: Failed to generate SQL: {str(e)}"

    def explain_results(self, question: str, sql: str, columns: list, rows: list) -> str:
        """Ask Ollama to explain query results in plain English."""
        display_rows = rows[:30] if len(rows) > 30 else rows

        prompt = f"""The user asked: "{question}"

This SQL query was executed:
{sql}

The query returned {len(rows)} rows. Here are the results:
Columns: {columns}
Data (first {len(display_rows)} rows): {display_rows}

Please provide a clear, concise explanation of these results in 2-4 sentences.
Focus on the key insights and numbers. Use natural language, not technical jargon.
If there are monetary values, format them nicely (e.g., £14.7M instead of 14723147.50).
Do NOT include any SQL or code in your response."""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3}
            )
            return response["message"]["content"].strip()
        except Exception as e:
            return f"Results returned {len(rows)} rows with columns: {columns}"

    def recommend_chart(self, question: str, columns: list, rows: list) -> dict:
        """Recommend best chart type for the data."""
        if not rows or len(rows) == 0:
            return {"chart_type": "table"}
        if len(rows) == 1 and len(columns) == 1:
            return {"chart_type": "table"}
        if len(rows) > 100:
            return {"chart_type": "table"}

        sample_rows = rows[:10]

        prompt = f"""Analyze this query result and recommend the best chart type.

COLUMNS: {columns}
SAMPLE DATA: {sample_rows}
TOTAL ROWS: {len(rows)}

Choose ONE chart type: "bar", "line", "pie", "scatter", or "table"

Rules:
- "bar" for comparing categories
- "line" for trends over time
- "pie" for proportions with 2-8 categories
- "scatter" for relationships
- "table" if not suitable for visualization

Respond ONLY with valid JSON (no markdown):
{{"chart_type": "bar", "x_column": "country", "y_column": "revenue", "title": "Revenue by Country", "reason": "Comparing categories"}}"""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0}
            )

            response_text = response["message"]["content"].strip()

            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            chart_config = json.loads(response_text)

            valid_types = ["bar", "line", "pie", "scatter", "table"]
            if chart_config.get("chart_type") not in valid_types:
                return {"chart_type": "table"}

            if chart_config["chart_type"] != "table":
                if chart_config.get("x_column") not in columns:
                    return {"chart_type": "table"}
                if chart_config.get("y_column") not in columns:
                    return {"chart_type": "table"}

            return chart_config
        except Exception as e:
            return {"chart_type": "table"}

    def chat(self, question: str, connector: BaseConnector) -> dict:
        """Main chat method — same interface as AIChatService."""
        from app.core.validators import is_safe_select_query

        schema = self.get_schema_description(connector)
        sql = self.generate_sql(question, schema)

        if sql.startswith("ERROR:"):
            return {
                "user_message": question,
                "generated_sql": None,
                "ai_response": sql,
                "query_success": False,
                "columns": [],
                "rows": []
            }

        is_safe, reason = is_safe_select_query(sql)
        if not is_safe:
            return {
                "user_message": question,
                "generated_sql": sql,
                "ai_response": f"I cannot execute this query for safety reasons: {reason}",
                "query_success": False,
                "columns": [],
                "rows": []
            }

        result = connector.execute_query(sql)

        if result["success"]:
            explanation = self.explain_results(question, sql, result["columns"], result["rows"])
            chart_config = self.recommend_chart(question, result["columns"], result["rows"])

            return {
                "user_message": question,
                "generated_sql": sql,
                "ai_response": explanation,
                "query_success": True,
                "columns": result["columns"],
                "rows": result["rows"][:50],
                "chart_config": chart_config
            }
        else:
            return {
                "user_message": question,
                "generated_sql": sql,
                "ai_response": f"The query had an error: {result['error']}",
                "query_success": False,
                "columns": [],
                "rows": []
            }