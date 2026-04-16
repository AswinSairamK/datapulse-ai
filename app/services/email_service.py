# ============================================================
# email_service.py — Email notification service
# ============================================================
# Sends email alerts via SMTP when data quality issues are found.
#
# Uses Gmail SMTP by default but works with any SMTP server.
# Emails are HTML-formatted with a professional template.
# ============================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app.core.config import (
    SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
    SMTP_FROM_NAME, ALERT_EMAIL_TO
)


class EmailService:
    """
    Sends email notifications for data quality alerts.
    """

    def __init__(self):
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.from_name = SMTP_FROM_NAME

    def send_email(self, to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
        """
        Send an email via SMTP.
        
        Returns:
            (True, "sent") on success
            (False, "error message") on failure
        """
        try:
            # Build the email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.username}>"
            msg["To"] = to_email

            # Attach HTML version
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

            # Connect to SMTP server and send
            # smtplib.SMTP automatically uses STARTTLS for port 587
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # Encrypt the connection
                server.login(self.username, self.password)
                server.send_message(msg)

            return True, "Email sent successfully"

        except Exception as e:
            return False, f"Failed to send email: {str(e)}"

    def send_dq_alert(self, data_source_name: str, results: dict, to_email: str = None) -> tuple[bool, str]:
        """
        Send a data quality alert email when checks fail.
        
        Called by the scheduler when score drops below threshold
        or when critical checks fail.
        """
        if to_email is None:
            to_email = ALERT_EMAIL_TO

        score = results.get("overall_score", 0)
        passed = results.get("passed", 0)
        failed = results.get("failed", 0)
        total = results.get("total_rules", 0)
        check_results = results.get("results", [])

        # Determine severity based on score
        if score < 50:
            severity = "CRITICAL"
            color = "#C62828"
        elif score < 70:
            severity = "WARNING"
            color = "#F57F17"
        else:
            severity = "INFO"
            color = "#1976D2"

        # Build the failed checks list
        failed_checks_html = ""
        for check in check_results:
            if not check.get("passed"):
                failed_checks_html += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{check.get('table', '-')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{check.get('column', '-')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{check.get('check_type', '-')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{check.get('actual_value', '-')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: {color};">FAIL</td>
                </tr>
                """

        if not failed_checks_html:
            failed_checks_html = '<tr><td colspan="5" style="padding: 12px; text-align: center; color: #666;">All checks passed!</td></tr>'

        # Build the email HTML
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
            <div style="background: white; padding: 30px; border-radius: 8px; border-top: 4px solid {color};">
                <h2 style="margin: 0 0 8px; color: #333;">DataPulse AI Alert</h2>
                <p style="margin: 0 0 24px; color: #666; font-size: 14px;">{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                
                <div style="background: {color}15; padding: 16px; border-radius: 6px; margin-bottom: 24px;">
                    <p style="margin: 0; font-size: 13px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">Severity</p>
                    <p style="margin: 4px 0 0; font-size: 20px; font-weight: 600; color: {color};">{severity}</p>
                </div>
                
                <h3 style="color: #333; margin: 0 0 12px;">Data Source</h3>
                <p style="margin: 0 0 24px; color: #555; font-size: 16px;"><strong>{data_source_name}</strong></p>
                
                <h3 style="color: #333; margin: 0 0 12px;">Health Score</h3>
                <div style="display: flex; gap: 12px; margin-bottom: 24px;">
                    <div style="flex: 1; background: #f9f9f9; padding: 16px; border-radius: 6px; text-align: center;">
                        <p style="margin: 0; font-size: 12px; color: #666;">SCORE</p>
                        <p style="margin: 4px 0 0; font-size: 28px; font-weight: 600; color: {color};">{score}/100</p>
                    </div>
                    <div style="flex: 1; background: #f9f9f9; padding: 16px; border-radius: 6px; text-align: center;">
                        <p style="margin: 0; font-size: 12px; color: #666;">PASSED</p>
                        <p style="margin: 4px 0 0; font-size: 28px; font-weight: 600; color: #2E7D32;">{passed}</p>
                    </div>
                    <div style="flex: 1; background: #f9f9f9; padding: 16px; border-radius: 6px; text-align: center;">
                        <p style="margin: 0; font-size: 12px; color: #666;">FAILED</p>
                        <p style="margin: 4px 0 0; font-size: 28px; font-weight: 600; color: #C62828;">{failed}</p>
                    </div>
                </div>
                
                <h3 style="color: #333; margin: 0 0 12px;">Failed Checks</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <thead>
                        <tr style="background: #f5f5f5;">
                            <th style="padding: 10px; text-align: left;">Table</th>
                            <th style="padding: 10px; text-align: left;">Column</th>
                            <th style="padding: 10px; text-align: left;">Check Type</th>
                            <th style="padding: 10px; text-align: left;">Actual</th>
                            <th style="padding: 10px; text-align: left;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {failed_checks_html}
                    </tbody>
                </table>
                
                <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #eee; color: #999; font-size: 12px; text-align: center;">
                    This alert was automatically generated by DataPulse AI.<br>
                    Visit your dashboard to view full details and take action.
                </div>
            </div>
        </body>
        </html>
        """

        subject = f"[{severity}] DataPulse Alert: {data_source_name} — Score: {score}/100"
        return self.send_email(to_email, subject, html_body)