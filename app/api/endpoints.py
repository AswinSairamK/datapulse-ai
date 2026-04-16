# ============================================================
# endpoints.py — FastAPI route handlers (the API endpoints)
# ============================================================
# This file defines what happens when someone calls our API:
#
# POST   /api/data-sources          → Add a new database connection
# GET    /api/data-sources          → List all connected databases
# POST   /api/data-sources/test     → Test a database connection
# GET    /api/data-sources/{id}/tables → List tables in a database
# GET    /api/data-sources/{id}/tables/{name}/columns → List columns
# POST   /api/rules                 → Add a monitoring rule
# GET    /api/rules/{data_source_id} → List rules for a database
# DELETE /api/rules/{rule_id}       → Delete a rule
#
# Each function handles one endpoint.
# FastAPI automatically:
# - Parses JSON from the request body
# - Validates it against our Pydantic schemas
# - Returns JSON responses
# - Generates API documentation at /docs
# ============================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.models.models import DataSource, MonitoringRule
from app.schemas.schemas import (
    DataSourceCreate, DataSourceResponse,
    RuleCreate, RuleResponse,
)
from app.services.db_connector import DatabaseConnector
from app.models.models import DataSource, MonitoringRule, ChatHistory
from app.schemas.schemas import (
    DataSourceCreate, DataSourceResponse,
    RuleCreate, RuleResponse,
    ChatRequest, ChatResponse,
)
from app.services.db_connector import DatabaseConnector
from app.services.ai_chat import AIChatService
from app.core.security import encrypt_password, decrypt_password

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.audit import log_action
from app.core.rate_limiter import limiter

from app.schemas.schemas import MaskingRuleCreate, MaskingRuleResponse
from app.models.models import MaskingRule
from app.services.data_masker import DataMasker

from app.core.auth import get_current_user
from app.models.models import User
from app.services.ai_factory import get_ai_chat_service

# Create a router — a group of related endpoints
# All endpoints defined here will be prefixed with /api when mounted
router = APIRouter()


# ============================================================
# DATA SOURCE ENDPOINTS
# ============================================================

@router.post("/data-sources", response_model=DataSourceResponse)
@limiter.limit("5/minute")
def create_data_source(
    source: DataSourceCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new database connection."""
    connector = DatabaseConnector(
        host=source.host, port=source.port,
        database=source.database_name,
        username=source.username,
        password=source.password,
        db_type=source.db_type
    )
    success, message = connector.test_connection()

    if not success:
        raise HTTPException(status_code=400, detail=message)

    source_data = source.model_dump()
    source_data["password"] = encrypt_password(source.password)

    db_source = DataSource(
        **source_data,
        user_id=current_user.id,
        last_connected=datetime.utcnow()
    )

    db.add(db_source)
    db.commit()
    db.refresh(db_source)

    log_action(
        db=db,
        action="data_source_created",
        user_id=current_user.id,
        resource_type="data_source",
        resource_id=str(db_source.id),
        details=f"User {current_user.email} connected database '{source.name}'",
        request=request
    )

    return db_source

@router.get("/data-sources", response_model=list[DataSourceResponse])
def list_data_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all data sources for the current user."""
    return db.query(DataSource).filter(DataSource.user_id == current_user.id).all()

@router.post("/data-sources/test")
def test_connection(source: DataSourceCreate):
    """
    Test a database connection without saving it.
    
    Used by the "Test Connection" button in the UI.
    The user enters their details, clicks test, and we try connecting.
    If it works, they can then click "Save".
    """
    connector = DatabaseConnector(
        host=source.host,
        port=source.port,
        database=source.database_name,
        username=source.username,
        password=source.password
    )
    success, message = connector.test_connection()
    return {"success": success, "message": message}


@router.get("/data-sources/{source_id}/tables")
def get_tables(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all tables in a connected database."""
    source = db.query(DataSource).filter(
        DataSource.id == source_id,
        DataSource.user_id == current_user.id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    connector = DatabaseConnector(
        host=source.host, port=source.port,
        database=source.database_name,
        username=source.username,
        password=decrypt_password(source.password),
        db_type=source.db_type
    )
    tables = connector.get_tables()
    return {"tables": tables}

@router.get("/data-sources/{source_id}/tables/{table_name}/columns")
def get_columns(
    source_id: int,
    table_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all columns in a specific table."""
    source = db.query(DataSource).filter(
        DataSource.id == source_id,
        DataSource.user_id == current_user.id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    connector = DatabaseConnector(
        host=source.host, port=source.port,
        database=source.database_name,
        username=source.username,
        password=decrypt_password(source.password),
        db_type=source.db_type
    )
    columns = connector.get_columns(table_name)
    return {"columns": columns}


# ============================================================
# MONITORING RULE ENDPOINTS
# ============================================================

@router.post("/rules", response_model=RuleResponse)
@limiter.limit("30/minute")
def create_rule(
    rule: RuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new monitoring rule."""
    from app.core.validators import is_safe_identifier, validate_table_name, validate_column_name, validate_numeric

    source = db.query(DataSource).filter(
        DataSource.id == rule.data_source_id,
        DataSource.user_id == current_user.id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    if not is_safe_identifier(rule.table_name):
        raise HTTPException(status_code=400, detail=f"Invalid table name '{rule.table_name}'")
    if rule.column_name and not is_safe_identifier(rule.column_name):
        raise HTTPException(status_code=400, detail=f"Invalid column name '{rule.column_name}'")
    if not validate_numeric(rule.min_value):
        raise HTTPException(status_code=400, detail="min_value must be numeric")
    if not validate_numeric(rule.max_value):
        raise HTTPException(status_code=400, detail="max_value must be numeric")

    connector = DatabaseConnector(
        host=source.host, port=source.port,
        database=source.database_name,
        username=source.username,
        password=decrypt_password(source.password),
        db_type=source.db_type
    )

    if not validate_table_name(connector, rule.table_name):
        raise HTTPException(status_code=400, detail=f"Table '{rule.table_name}' does not exist")
    if rule.column_name and not validate_column_name(connector, rule.table_name, rule.column_name):
        raise HTTPException(status_code=400, detail=f"Column '{rule.column_name}' does not exist")

    db_rule = MonitoringRule(**rule.model_dump(), user_id=current_user.id)
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)

    return db_rule

@router.get("/rules/{data_source_id}", response_model=list[RuleResponse])
def list_rules(
    data_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all monitoring rules for a specific data source (only if owned by user)."""
    # Verify ownership
    source = db.query(DataSource).filter(
        DataSource.id == data_source_id,
        DataSource.user_id == current_user.id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    rules = db.query(MonitoringRule).filter(
        MonitoringRule.data_source_id == data_source_id,
        MonitoringRule.user_id == current_user.id
    ).all()
    return rules

# ============================================================
# CHAT ENDPOINT
# ============================================================

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat_with_data(
    request_body: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Chat with your database using natural language."""
    source = db.query(DataSource).filter(
        DataSource.id == request_body.data_source_id,
        DataSource.user_id == current_user.id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    connector = DatabaseConnector(
        host=source.host, port=source.port,
        database=source.database_name,
        username=source.username,
        password=decrypt_password(source.password),
        db_type=source.db_type
    )

    ai_service = get_ai_chat_service()
    result = ai_service.chat(request_body.message, connector)

    if result["query_success"] and result.get("rows"):
        masker = DataMasker(db)
        masked_rows = masker.mask_all_tables_result(
            data_source_id=request_body.data_source_id,
            columns=result["columns"],
            rows=result["rows"]
        )
        if masked_rows != result["rows"]:
            explanation = ai_service.explain_results(
                request_body.message,
                result["generated_sql"],
                result["columns"],
                masked_rows
            )
            result["ai_response"] = explanation
            result["rows"] = masked_rows

    chat_record = ChatHistory(
        data_source_id=request_body.data_source_id,
        user_id=current_user.id,
        user_message=result["user_message"],
        generated_sql=result["generated_sql"],
        ai_response=result["ai_response"],
        query_success=result["query_success"],
    )
    db.add(chat_record)
    db.commit()

    return ChatResponse(
        user_message=result["user_message"],
        generated_sql=result["generated_sql"],
        ai_response=result["ai_response"],
        query_success=result["query_success"],
        created_at=chat_record.created_at,
        columns=result.get("columns"),
        rows=result.get("rows"),
        chart_config=result.get("chart_config"),
    )

# ============================================================
# DQ CHECK ENDPOINTS
# ============================================================

from app.services.dq_engine import DQEngine

@router.post("/checks/run/{data_source_id}")
@limiter.limit("10/minute")
def run_checks(
    data_source_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run all active DQ checks for a data source.
    Returns health score and individual check results.
    """
    engine = DQEngine(db)
    results = engine.run_checks_for_source(data_source_id, user_id=current_user.id)
    return results

@router.get("/checks/results/{data_source_id}")
def get_check_results(data_source_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Get recent check results for a data source."""
    from app.models.models import CheckResult
    results = db.query(CheckResult).filter(
        CheckResult.data_source_id == data_source_id
    ).order_by(CheckResult.checked_at.desc()).limit(limit).all()

    return {"results": [
        {
            "id": r.id,
            "table": r.table_name,
            "column": r.column_name,
            "check_type": r.check_type,
            "passed": r.passed,
            "actual_value": r.actual_value,
            "expected_value": r.expected_value,
            "message": r.message,
            "score": r.score,
            "checked_at": r.checked_at.isoformat(),
        } for r in results
    ]}

# ============================================================
# AI SUGGEST ENDPOINTS
# ============================================================

from app.services.ai_suggest import AISuggestService

@router.get("/suggest/{data_source_id}/{table_name}")
@limiter.limit("5/minute")
def suggest_rules(data_source_id: int, table_name: str,request: Request, db: Session = Depends(get_db)):
    """AI analyzes a table and suggests data quality rules."""
    source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    connector = DatabaseConnector(
        host=source.host, port=source.port,
        database=source.database_name,
        username=source.username,
        password=decrypt_password(source.password), 
        db_type=source.db_type
    )

    ai_suggest = AISuggestService()
    suggestions = ai_suggest.suggest_rules(connector, table_name)

    return {"table": table_name, "suggestions": suggestions}


@router.post("/suggest/accept")
def accept_suggestion(rule: RuleCreate, db: Session = Depends(get_db)):
    """
    Accept an AI-suggested rule — saves it as an active monitoring rule.
    Same as creating a rule manually, but called from the suggestions UI.
    """
    source = db.query(DataSource).filter(DataSource.id == rule.data_source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    db_rule = MonitoringRule(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a monitoring rule."""
    rule = db.query(MonitoringRule).filter(MonitoringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule_details = f"{rule.check_type} on {rule.table_name}.{rule.column_name or '*'}"
    db.delete(rule)
    db.commit()

    log_action(
        db=db,
        action="rule_deleted",
        resource_type="rule",
        resource_id=str(rule_id),
        details=f"Deleted rule: {rule_details}",
        request=request
    )

    return {"message": "Rule deleted successfully"}



# ============================================================
# AUDIT LOG ENDPOINTS
# ============================================================

@router.get("/audit-logs")
def get_audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    """Get recent audit log entries."""
    from app.models.models import AuditLog
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    return {"logs": [
        {
            "id": log.id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "success": log.success,
            "error_message": log.error_message,
            "timestamp": log.timestamp.isoformat(),
        } for log in logs
    ]}

# ============================================================
# MASKING RULE ENDPOINTS
# ============================================================

@router.post("/masking-rules", response_model=MaskingRuleResponse)
def create_masking_rule(rule: MaskingRuleCreate, request: Request, db: Session = Depends(get_db)):
    """
    Create a new data masking rule for a sensitive column.
    """
    from app.core.validators import is_safe_identifier
    
    # Safety checks
    if not is_safe_identifier(rule.table_name):
        raise HTTPException(status_code=400, detail="Invalid table name")
    if not is_safe_identifier(rule.column_name):
        raise HTTPException(status_code=400, detail="Invalid column name")
    
    valid_types = ["email", "phone", "address", "name", "credit_card", "ssn", "full", "custom"]
    if rule.mask_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mask_type. Must be one of: {', '.join(valid_types)}"
        )
    
    source = db.query(DataSource).filter(DataSource.id == rule.data_source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    db_rule = MaskingRule(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    log_action(
        db=db,
        action="masking_rule_created",
        resource_type="masking_rule",
        resource_id=str(db_rule.id),
        details=f"Mask {rule.mask_type} on {rule.table_name}.{rule.column_name}",
        request=request
    )
    
    return db_rule


@router.get("/masking-rules/{data_source_id}", response_model=list[MaskingRuleResponse])
def list_masking_rules(data_source_id: int, db: Session = Depends(get_db)):
    """List all masking rules for a data source."""
    rules = db.query(MaskingRule).filter(
        MaskingRule.data_source_id == data_source_id
    ).all()
    return rules


@router.delete("/masking-rules/{rule_id}")
def delete_masking_rule(rule_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a masking rule."""
    rule = db.query(MaskingRule).filter(MaskingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Masking rule not found")
    
    db.delete(rule)
    db.commit()
    
    log_action(
        db=db,
        action="masking_rule_deleted",
        resource_type="masking_rule",
        resource_id=str(rule_id),
        request=request
    )
    
    return {"message": "Masking rule deleted"}


# ============================================================
# EMAIL ALERT ENDPOINTS
# ============================================================

@router.post("/alerts/test/{data_source_id}")
def test_alert(data_source_id: int, db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    """
    Manually trigger a data quality check and send an email alert.
    Used to test the email setup.
    """
    from app.services.email_service import EmailService
    
    source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    # Run the checks
    engine = DQEngine(db)
    results = engine.run_checks_for_source(data_source_id,  user_id=current_user.id)
    
    if "error" in results:
        raise HTTPException(status_code=400, detail=results["error"])
    
    # Send the email
    email_service = EmailService()
    success, message = email_service.send_dq_alert(
        data_source_name=source.name,
        results=results
    )
    
    return {
        "email_sent": success,
        "message": message,
        "score": results.get("overall_score"),
        "failed_checks": results.get("failed")
    }