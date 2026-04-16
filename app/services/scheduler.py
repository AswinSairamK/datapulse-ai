# ============================================================
# scheduler.py — Background job scheduler
# ============================================================
# Runs DQ checks automatically at set intervals
# so users don't have to manually click "Run checks"
# ============================================================

from apscheduler.schedulers.background import BackgroundScheduler
from app.core.database import SessionLocal
from app.services.dq_engine import DQEngine
from app.models.models import DataSource
from datetime import datetime


scheduler = BackgroundScheduler()


def run_all_checks():
    """
    Runs DQ checks for every active data source.
    Sends email alerts when checks fail or scores drop.
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scheduler: Running automated DQ checks...")
    
    db = SessionLocal()
    try:
        from app.core.config import ALERT_SCORE_THRESHOLD
        from app.services.email_service import EmailService
        
        sources = db.query(DataSource).filter(DataSource.is_active == True).all()
        email_service = EmailService()
        
        for source in sources:
            print(f"  Checking: {source.name}...")
            engine = DQEngine(db)
            result = engine.run_checks_for_source(source.id,  user_id=source.user_id)
            
            if "error" in result:
                print(f"    Error: {result['error']}")
                continue
            
            score = result.get("overall_score", 100)
            failed = result.get("failed", 0)
            print(f"    Score: {score}/100 | Passed: {result['passed']} | Failed: {failed}")
            
            # Send alert if score is below threshold OR any checks failed
            if score < ALERT_SCORE_THRESHOLD or failed > 0:
                print(f"    Sending alert email...")
                success, msg = email_service.send_dq_alert(
                    data_source_name=source.name,
                    results=result
                )
                if success:
                    print(f"    Alert email sent successfully")
                else:
                    print(f"    Alert email failed: {msg}")
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Scheduler: Completed.\n")
    except Exception as e:
        print(f"  Scheduler error: {e}")
    finally:
        db.close()


def start_scheduler(interval_minutes: int = 60):
    """Start the background scheduler."""
    scheduler.add_job(
        run_all_checks,
        'interval',
        minutes=interval_minutes,
        id='dq_checks',
        replace_existing=True
    )
    scheduler.start()
    print(f"Scheduler started — running checks every {interval_minutes} minutes")


def stop_scheduler():
    """Stop the background scheduler."""
    scheduler.shutdown()
    print("Scheduler stopped")