# ============================================================
# models.py — Defines the database tables as Python classes
# ============================================================
# Each class here becomes a table in PostgreSQL.
# Each attribute becomes a column.
#
# For example, the DataSource class below becomes a table called
# "data_sources" with columns: id, name, host, port, etc.
#
# SQLAlchemy handles the CREATE TABLE SQL for us.
# ============================================================

from sqlalchemy import (
    Column,         # Defines a column in a table
    Integer,        # Integer data type (1, 2, 3...)
    String,         # Text data type ("hello", "world")
    Float,          # Decimal numbers (3.14, 99.99)
    Boolean,        # True or False
    DateTime,       # Date and time (2026-04-03 14:30:00)
    Text,           # Long text (for storing SQL queries, JSON, etc.)
    ForeignKey,     # Links one table to another (like a relationship)
)
from sqlalchemy.orm import relationship  # Defines relationships between tables
from datetime import datetime
from app.core.database import Base       # The parent class all models inherit from

class User(Base):
    """
    Stores user accounts.
    Each user has their own isolated set of data sources, rules, and chat history.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DataSource(Base):
    """
    Stores database connections that the user has added.
    
    Example: A user connects their e-commerce PostgreSQL database.
    We save the connection details here so we can connect to it
    later when running DQ checks or answering chat questions.
    
    Each row = one connected database.
    """
    __tablename__ = "data_sources"  # This becomes the actual table name in PostgreSQL

    # --- Columns ---

    # Primary key: a unique auto-incrementing ID for each data source.
    # If you add 3 databases, they get IDs 1, 2, 3.
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # A friendly name the user gives this connection (e.g., "Production DB", "Staging")
    name = Column(String(100), nullable=False)

    # Connection details — everything needed to connect to the user's database
    host = Column(String(255), nullable=False)       # e.g., "localhost" or "db.company.com"
    port = Column(String(10), default="5432")        # PostgreSQL default port
    database_name = Column(String(100), nullable=False)  # e.g., "ecommerce_db"
    username = Column(String(100), nullable=False)   # e.g., "postgres"
    password = Column(String(255), nullable=False)   # Stored as-is (in production, encrypt this)
    db_type = Column(String(20), default="postgresql")  # postgresql or mysql

    # Status tracking
    is_active = Column(Boolean, default=True)        # Can be deactivated without deleting
    last_connected = Column(DateTime, nullable=True) # When we last successfully connected
    created_at = Column(DateTime, default=datetime.utcnow)  # When this was first added

    # --- Relationships ---
    # One data source can have many monitoring rules.
    # "cascade=all, delete-orphan" means: if we delete a data source,
    # automatically delete all its rules too (don't leave orphan records).
    rules = relationship("MonitoringRule", back_populates="data_source", cascade="all, delete-orphan")
    check_results = relationship("CheckResult", back_populates="data_source", cascade="all, delete-orphan")
    chat_history = relationship("ChatHistory", back_populates="data_source", cascade="all, delete-orphan")


class MonitoringRule(Base):
    """
    Stores the data quality rules the user has defined.
    
    Example rules:
    - "customer_id in the orders table should never be null"
    - "price should be between 0 and 50000"
    - "order_id should have no duplicates"
    - "updated_at should be within the last 24 hours"
    
    Each row = one rule for one column in one table.
    """
    __tablename__ = "monitoring_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Which data source does this rule belong to?
    # ForeignKey creates a link to the data_sources table.
    # If data_source_id = 1, this rule monitors a table in data source #1.
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)

    # What table and column are we monitoring?
    table_name = Column(String(100), nullable=False)   # e.g., "orders"
    column_name = Column(String(100), nullable=True)   # e.g., "customer_id" (null for table-level checks)

    # What type of check?
    # Options: "null_check", "range_check", "duplicate_check", "freshness_check", "custom_sql"
    check_type = Column(String(50), nullable=False)

    # Check parameters — stored as text, interpreted based on check_type
    # For range_check: min_value="0", max_value="50000"
    # For freshness_check: max_value="24" (hours)
    # For custom_sql: custom_sql="SELECT COUNT(*) FROM orders WHERE status = 'invalid'"
    min_value = Column(String(50), nullable=True)
    max_value = Column(String(50), nullable=True)
    custom_sql = Column(Text, nullable=True)

    # How severe is a failure?
    # "critical" = health score drops a lot
    # "warning" = small drop
    # "info" = logged but doesn't affect score
    severity = Column(String(20), default="warning")

    # Is this rule currently active?
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # --- Relationships ---
    data_source = relationship("DataSource", back_populates="rules")
    check_results = relationship("CheckResult", back_populates="rule", cascade="all, delete-orphan")


class CheckResult(Base):
    """
    Stores the result of every DQ check that has ever run.
    
    Every time the scheduler runs checks (say every hour), it creates
    one CheckResult for each rule. Over time, this builds up a history
    that we can use to show trends ("null rate was 0.1% last week,
    now it's 1.8% — something changed").
    
    Each row = one check execution for one rule at one point in time.
    """
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Links to which data source and rule this result belongs to
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("monitoring_rules.id"), nullable=False)

    # What table/column was checked?
    table_name = Column(String(100), nullable=False)
    column_name = Column(String(100), nullable=True)
    check_type = Column(String(50), nullable=False)

    # Did it pass or fail?
    passed = Column(Boolean, nullable=False)

    # The actual measured value (what we found)
    # e.g., "null_percentage": 1.8, "duplicate_count": 14, "max_value": 82340
    actual_value = Column(String(255), nullable=True)

    # The expected value (what the rule says it should be)
    # e.g., "max_null_percentage": 0, "max_value": 50000
    expected_value = Column(String(255), nullable=True)

    # A human-readable message explaining the result
    # e.g., "Found 14 duplicate order_id values" or "All values within range"
    message = Column(Text, nullable=True)

    # Health score impact (0-100, how much this check contributed to the overall score)
    score = Column(Float, default=100.0)

    # When this check was executed
    checked_at = Column(DateTime, default=datetime.utcnow)

    # --- Relationships ---
    data_source = relationship("DataSource", back_populates="check_results")
    rule = relationship("MonitoringRule", back_populates="check_results")


class ChatHistory(Base):
    """
    Stores every conversation the user has with the AI chat module.
    
    Each row = one message (either from the user or from the AI).
    We store both the question and the generated SQL so the user
    can see exactly what query the AI ran.
    
    This also lets us show chat history when the user comes back later.
    """
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Which database was the user chatting about?
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)

    # The user's question in plain English
    # e.g., "Which customers spent more than $5000 last quarter?"
    user_message = Column(Text, nullable=False)

    # The SQL query that the AI generated from the question
    # e.g., "SELECT customer_id, SUM(amount) FROM orders WHERE..."
    generated_sql = Column(Text, nullable=True)

    # The AI's response (explanation + summary of results)
    ai_response = Column(Text, nullable=True)

    # Did the query run successfully?
    # False if the AI generated invalid SQL or the query errored
    query_success = Column(Boolean, default=True)

    # When this conversation happened
    created_at = Column(DateTime, default=datetime.utcnow)

    # --- Relationships ---
    data_source = relationship("DataSource", back_populates="chat_history")

class AuditLog(Base):
    """
    Stores a record of every important action taken in the system.
    
    Used for:
    - Security investigations ("who deleted that rule?")
    - Compliance reporting
    - Debugging ("what happened before the error?")
    - Usage analytics
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # What happened
    action = Column(String(100), nullable=False)
    # Examples: "data_source_created", "rule_deleted", "chat_query", 
    #           "dq_check_run", "ai_suggestion_requested"
    
    # What resource was affected (optional)
    resource_type = Column(String(50), nullable=True)
    # Examples: "data_source", "rule", "chat", "check"
    
    resource_id = Column(String(50), nullable=True)
    # The ID of the affected resource, as string
    
    # Details about the action (optional)
    details = Column(Text, nullable=True)
    # Human-readable description of what happened
    
    # Request metadata
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    
    # Status
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # When it happened
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class MaskingRule(Base):
    """
    Stores data masking rules for sensitive columns.
    
    When DataPulse fetches data from a user's database,
    it checks if any columns have masking rules and applies
    the appropriate masking before sending results to AI
    or displaying in the dashboard.
    
    Example:
        table: customers
        column: email
        mask_type: email
        → converts "john@example.com" to "****@example.com"
    """
    __tablename__ = "masking_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    
    table_name = Column(String(100), nullable=False)
    column_name = Column(String(100), nullable=False)
    
    # Type of masking to apply
    # Options: "email", "phone", "address", "name", "credit_card", "ssn", "full", "custom"
    mask_type = Column(String(50), nullable=False)
    
    # For custom masking — how many characters to keep visible
    visible_start = Column(Integer, default=0)  # Characters visible at start
    visible_end = Column(Integer, default=0)    # Characters visible at end
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    data_source = relationship("DataSource")
