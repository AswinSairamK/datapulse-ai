# ============================================================
# ai_chat.py — AI Chat Service (Gemini-powered)
# ============================================================
# This is the brain of the chat module.
#
# Flow:
# 1. User asks: "Which country has the highest revenue?"
# 2. We send the question + table schema to Gemini
# 3. Gemini generates a SQL query
# 4. We run that SQL against the user's database
# 5. We send the results back to Gemini
# 6. Gemini explains the results in plain English
# 7. We return everything to the user
# ============================================================


from app.services.db_connector import DatabaseConnector
from app.services.db_connector import DatabaseConnector
from groq import Groq
from app.core.config import GROQ_API_KEY, GROQ_MODEL
from app.services.db_connector import DatabaseConnector

class AIChatService:
    """
    Handles the full cycle:
    English question → SQL → Execute → Explain results
    """

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL

    def recommend_chart(self, question: str, columns: list, rows: list) -> dict:
        """
        Analyze query results and recommend the best chart type.
        
        Returns a dict with:
        {
            "chart_type": "bar" | "line" | "pie" | "scatter" | "table",
            "x_column": "column_name_for_x_axis",
            "y_column": "column_name_for_y_axis", 
            "title": "Suggested chart title",
            "reason": "Why this chart type"
        }
        
        If no chart is suitable, returns {"chart_type": "table"}.
        """
        # Don't try to chart if no data or too many rows
        if not rows or len(rows) == 0:
            return {"chart_type": "table"}
        
        # If only 1 row and 1 column, it's a single value — no chart needed
        if len(rows) == 1 and len(columns) == 1:
            return {"chart_type": "table"}
        
        # Too many rows for a chart — show as table
        if len(rows) > 100:
            return {"chart_type": "table"}
        
        # Analyze sample data for the AI
        sample_rows = rows[:10]
        
        prompt = f"""You are a data visualization expert. Analyze this query result and recommend the best chart type.

USER QUESTION: {question}

COLUMNS: {columns}
SAMPLE DATA (first 10 rows): {sample_rows}
TOTAL ROWS: {len(rows)}

Choose ONE of these chart types:
- "bar" — comparing categories (e.g., revenue by country, sales by product)
- "line" — trends over time (e.g., monthly revenue, daily users)
- "pie" — parts of a whole (use only if 2-8 categories, showing proportions)
- "scatter" — relationship between two numeric variables
- "table" — if the data is not suitable for visualization

Rules:
1. For time-series data (dates, months, years), prefer "line"
2. For category comparisons, prefer "bar"
3. For proportions with few categories, "pie" is good
4. If the data has more than 2 meaningful columns, prefer "bar" or "table"
5. If there's no clear numeric column, use "table"

Respond ONLY with valid JSON in this exact format (no markdown, no code blocks):
{{"chart_type": "bar", "x_column": "country", "y_column": "revenue", "title": "Revenue by Country", "reason": "Comparing revenue across categories"}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Clean up markdown if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            import json
            chart_config = json.loads(response_text)
            
            # Validate the chart config
            valid_types = ["bar", "line", "pie", "scatter", "table"]
            if chart_config.get("chart_type") not in valid_types:
                return {"chart_type": "table"}
            
            # Make sure the columns exist
            if chart_config["chart_type"] != "table":
                if chart_config.get("x_column") not in columns:
                    return {"chart_type": "table"}
                if chart_config.get("y_column") not in columns:
                    return {"chart_type": "table"}
            
            return chart_config
            
        except Exception as e:
            # If AI fails, fall back to table
            return {"chart_type": "table", "reason": f"Chart recommendation failed: {str(e)}"}

    def get_schema_description(self, connector: DatabaseConnector) -> str:
        """
        Build a text description of all tables and columns
        in the user's database.
        
        We send this to Gemini so it knows what tables exist,
        what columns they have, and what data types they use.
        Without this context, Gemini would have to guess table
        and column names — and would get them wrong.
        
        Example output:
        Table: raw_transactions
          - invoice (character varying, nullable)
          - stock_code (character varying, nullable)
          - quantity (integer, nullable)
          - price (numeric, nullable)
          ...
        """
        tables = connector.get_tables()
        schema_text = ""

        for table_info in tables:
            # Skip if there was an error getting tables
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
        """
        Send the user's question + database schema to Gemini
        and get back a SQL query.
        
        The prompt is carefully crafted:
        - We tell Gemini it's a PostgreSQL expert
        - We give it the exact schema (tables + columns + types)
        - We tell it to return ONLY the SQL, nothing else
        - We add safety rules (SELECT only, no modifications)
        
        This is called "prompt engineering" — the quality of the
        prompt directly affects the quality of the generated SQL.
        """
        prompt = f"""You are a PostgreSQL SQL expert. Given the following database schema, 
write a SQL query to answer the user's question.

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
8. For date-based questions, use PostgreSQL date functions like DATE_TRUNC, EXTRACT, TO_CHAR.

USER QUESTION: {question}

SQL QUERY:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            sql = response.choices[0].message.content.strip()

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
        """
        Send the query results back to Gemini and get a
        human-readable explanation.
        
        Instead of showing raw rows and columns, Gemini
        summarizes the findings in plain English.
        
        Example:
        Question: "Which country has the highest revenue?"
        SQL result: [["United Kingdom", 14723147.50]]
        
        Gemini's explanation:
        "The United Kingdom generated the highest revenue at £14.7M,
         which is significantly ahead of all other countries."
        """
        # Limit rows sent to Gemini to avoid token limits
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Results returned {len(rows)} rows with columns: {columns}"

    def chat(self, question: str, connector: DatabaseConnector) -> dict:
        """
        The main method — handles the full chat cycle.
        Now includes SQL safety validation before execution.
        """
        from app.core.validators import is_safe_select_query

        # Step 1: Get the schema
        schema = self.get_schema_description(connector)

        # Step 2: Ask Gemini to generate SQL
        sql = self.generate_sql(question, schema)

        # Check if SQL generation failed
        if sql.startswith("ERROR:"):
            return {
                "user_message": question,
                "generated_sql": None,
                "ai_response": sql,
                "query_success": False,
                "columns": [],
                "rows": []
            }

        # Step 3: SAFETY CHECK — validate the AI-generated SQL
        is_safe, reason = is_safe_select_query(sql)
        if not is_safe:
            return {
                "user_message": question,
                "generated_sql": sql,
                "ai_response": f"I cannot execute this query for safety reasons: {reason}. Please try rephrasing your question to ask only for information retrieval.",
                "query_success": False,
                "columns": [],
                "rows": []
            }

        # Step 4: Execute the SQL
        result = connector.execute_query(sql)

        # Step 5: Handle success or failure
        if result["success"]:
            explanation = self.explain_results(
                question, sql,
                result["columns"], result["rows"]
            )

            # Get chart recommendation
            chart_config = self.recommend_chart(
                question, result["columns"], result["rows"]
            )

            return {
                "user_message": question,
                "generated_sql": sql,
                "ai_response": explanation,
                "query_success": True,
                "columns": result["columns"],
                "rows": result["rows"][:50],
                "chart_config": chart_config
            }