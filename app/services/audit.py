# ============================================================
# audit.py — Audit logging service
# ============================================================
# Logs every important action for security and compliance.
# Simple helper functions that other code calls to record events.
# ============================================================

from sqlalchemy.orm import Session
from fastapi import Request
from app.models.models import AuditLog


def log_action(
    db: Session,
    action: str,
    user_id: int = None,
    resource_type: str = None,
    resource_id: str = None,
    details: str = None,
    success: bool = True,
    error_message: str = None,
    request: Request = None,
):
    """Record an action in the audit log."""
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")[:255]
    
    audit = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        success=success,
        error_message=error_message,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    db.add(audit)
    db.commit()
    return audit