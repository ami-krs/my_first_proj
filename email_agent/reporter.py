"""
Email Agent Reporting System
Generates detailed reports and sends them via email every 15 minutes
"""

from __future__ import annotations
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from .auth_manager import AuthManager
from .email_io import connect_smtp


@dataclass
class EmailEvent:
    """Represents an email processing event"""
    timestamp: str
    subject: str
    from_address: str
    action: str  # "processed", "skipped_spam", "skipped_auto", "error"
    reason: str
    agent_type: str = ""
    confidence: float = 0.0
    processing_time: float = 0.0


class EmailReporter:
    """Handles email processing reports and periodic email delivery"""
    
    def __init__(self, report_email: str, sender_email: str):
        """
        Initialize the reporter
        
        Args:
            report_email: Email address to send reports to
            sender_email: Email address to send reports from
        """
        self.report_email = report_email
        self.sender_email = sender_email
        self.events: List[EmailEvent] = []
        self.lock = threading.Lock()
        self.running = False
        self.report_thread = None
        
    def add_event(self, event: EmailEvent):
        """Add an email processing event"""
        with self.lock:
            self.events.append(event)
    
    def _get_credentials(self):
        """Get SMTP credentials for sending reports"""
        auth_manager = AuthManager(self.sender_email)
        creds = auth_manager.get_credentials()
        
        if not creds:
            raise ValueError(f"No stored credentials for {self.sender_email}")
        
        return creds
    
    def _send_report_email(self, report_html: str, report_text: str):
        """Send the report via email"""
        try:
            creds = self._get_credentials()
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Email Agent Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            msg['From'] = formataddr(("Email Agent Reporter", self.sender_email))
            msg['To'] = self.report_email
            
            # Add text and HTML versions
            text_part = MIMEText(report_text, 'plain')
            html_part = MIMEText(report_html, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Determine SMTP port - Gmail uses 587, try that first
            smtp_port = 587
            use_ssl = False
            use_starttls = True
            
            # Infer port from host
            if 'gmail' in creds.smtp_host.lower():
                smtp_port = 587  # Gmail default with STARTTLS
            elif 'outlook' in creds.smtp_host.lower() or 'office365' in creds.smtp_host.lower():
                smtp_port = 587
            else:
                smtp_port = 587  # Default
            
            print(f"📧 Sending report to {self.report_email} via {creds.smtp_host}:{smtp_port}...")
            
            # Use connect_smtp from email_io for consistency
            try:
                smtp_conn = connect_smtp(
                    host=creds.smtp_host,
                    port=smtp_port,
                    username=creds.username,
                    password=creds.smtp_password,
                    from_address=creds.username,
                    from_name="Email Agent Reporter",
                    use_starttls=use_starttls,
                    use_ssl=use_ssl
                )
                smtp_conn.server.send_message(msg)
                smtp_conn.server.quit()
            except Exception as smtp_error:
                # Fallback: try direct connection
                print(f"⚠️  connect_smtp failed, trying direct connection: {smtp_error}")
                if use_ssl:
                    server = smtplib.SMTP_SSL(creds.smtp_host, smtp_port)
                else:
                    server = smtplib.SMTP(creds.smtp_host, smtp_port)
                server.ehlo()
                if use_starttls and not use_ssl:
                    server.starttls()
                    server.ehlo()
                server.login(creds.username, creds.smtp_password)
                server.send_message(msg)
                server.quit()
            
            print(f"✅ Report sent successfully to {self.report_email}")
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ SMTP Authentication failed: {e}")
            print(f"   Please verify credentials for {self.sender_email}")
        except smtplib.SMTPException as e:
            print(f"❌ SMTP Error: {e}")
        except Exception as e:
            print(f"❌ Failed to send report: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_report(self) -> tuple[str, str]:
        """Generate HTML and text reports"""
        with self.lock:
            events = self.events.copy()
            self.events.clear()  # Clear after generating report
        
        if not events:
            # Send a "no activity" report
            html_report = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ background-color: #f0f0f0; padding: 15px; border-radius: 5px; }}
                    .no-activity {{ text-align: center; padding: 40px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>📧 Email Agent Report</h1>
                    <p><strong>Period:</strong> Last 15 minutes</p>
                    <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                <div class="no-activity">
                    <h2>No Email Activity</h2>
                    <p>No emails were processed in the last 15 minutes.</p>
                </div>
            </body>
            </html>
            """
            
            text_report = f"""
EMAIL AGENT REPORT
==================

Period: Last 15 minutes
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

STATUS
------
No Email Activity

No emails were processed in the last 15 minutes.
"""
            return html_report.strip(), text_report.strip()
        
        # Calculate statistics
        total_emails = len(events)
        processed = len([e for e in events if e.action == "processed"])
        skipped_spam = len([e for e in events if e.action == "skipped_spam"])
        skipped_auto = len([e for e in events if e.action == "skipped_auto"])
        errors = len([e for e in events if e.action == "error"])
        
        # Time range
        start_time = min(e.timestamp for e in events)
        end_time = max(e.timestamp for e in events)
        
        # Generate HTML report
        html_report = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 15px; border-radius: 5px; }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat-box {{ background-color: #e8f4fd; padding: 15px; border-radius: 5px; text-align: center; }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #1976d2; }}
                .stat-label {{ color: #666; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .processed {{ color: green; }}
                .skipped {{ color: orange; }}
                .error {{ color: red; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📧 Email Agent Report</h1>
                <p><strong>Period:</strong> {start_time} to {end_time}</p>
                <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{total_emails}</div>
                    <div class="stat-label">Total Emails</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{processed}</div>
                    <div class="stat-label">Processed</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{skipped_spam + skipped_auto}</div>
                    <div class="stat-label">Skipped</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{errors}</div>
                    <div class="stat-label">Errors</div>
                </div>
            </div>
            
            <h2>📋 Email Details</h2>
            <table>
                <tr>
                    <th>Time</th>
                    <th>From</th>
                    <th>Subject</th>
                    <th>Action</th>
                    <th>Reason</th>
                    <th>Agent</th>
                    <th>Confidence</th>
                </tr>
        """
        
        for event in events:
            action_class = ""
            if event.action == "processed":
                action_class = "processed"
            elif event.action.startswith("skipped"):
                action_class = "skipped"
            elif event.action == "error":
                action_class = "error"
            
            confidence_display = f"{event.confidence:.2f}" if event.confidence > 0 else "-"
            html_report += f"""
                <tr class="{action_class}">
                    <td>{event.timestamp}</td>
                    <td>{event.from_address}</td>
                    <td>{event.subject}</td>
                    <td>{event.action.replace('_', ' ').title()}</td>
                    <td>{event.reason}</td>
                    <td>{event.agent_type}</td>
                    <td>{confidence_display}</td>
                </tr>
            """
        
        html_report += """
            </table>
            
            <div class="footer">
                <p>This report was automatically generated by the Email Agent system.</p>
                <p>For questions or issues, please contact the system administrator.</p>
            </div>
        </body>
        </html>
        """
        
        # Generate text report
        text_report = f"""
EMAIL AGENT REPORT
==================

Period: {start_time} to {end_time}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

STATISTICS
----------
Total Emails: {total_emails}
Processed: {processed}
Skipped: {skipped_spam + skipped_auto}
  - Spam: {skipped_spam}
  - Auto: {skipped_auto}
Errors: {errors}

EMAIL DETAILS
-------------
"""
        
        for event in events:
            confidence_display = f"{event.confidence:.2f}" if event.confidence > 0 else "N/A"
            text_report += f"""
Time: {event.timestamp}
From: {event.from_address}
Subject: {event.subject}
Action: {event.action.replace('_', ' ').title()}
Reason: {event.reason}
Agent: {event.agent_type}
Confidence: {confidence_display}
Processing Time: {event.processing_time:.2f}s
{'='*50}
"""
        
        return html_report, text_report
    
    def _report_worker(self):
        """Background worker that sends reports every 15 minutes"""
        print(f"⏰ Report worker started - next report in 15 minutes")
        while self.running:
            time.sleep(900)  # 15 minutes = 900 seconds
            
            if self.running:  # Check again after sleep
                try:
                    print(f"📊 Generating report at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
                    html_report, text_report = self._generate_report()
                    if html_report and text_report:
                        self._send_report_email(html_report, text_report)
                    else:
                        print(f"⚠️  Empty report generated, skipping...")
                except Exception as e:
                    print(f"❌ Report generation failed: {e}")
                    import traceback
                    traceback.print_exc()
    
    def start_reporting(self):
        """Start the periodic reporting"""
        if self.running:
            return
        
        self.running = True
        self.report_thread = threading.Thread(target=self._report_worker, daemon=True)
        self.report_thread.start()
        print(f"📊 Reporting started - reports will be sent to {self.report_email} every 15 minutes")
    
    def stop_reporting(self):
        """Stop the periodic reporting"""
        self.running = False
        if self.report_thread:
            self.report_thread.join(timeout=5)
        print("📊 Reporting stopped")
    
    def send_immediate_report(self):
        """Send a report immediately"""
        try:
            html_report, text_report = self._generate_report()
            if html_report and text_report:
                self._send_report_email(html_report, text_report)
        except Exception as e:
            print(f"❌ Immediate report failed: {e}")


# Global reporter instance
_reporter: EmailReporter = None


def init_reporter(report_email: str, sender_email: str):
    """Initialize the global reporter"""
    global _reporter
    _reporter = EmailReporter(report_email, sender_email)
    _reporter.start_reporting()


def log_email_event(
    subject: str,
    from_address: str,
    action: str,
    reason: str,
    agent_type: str = "",
    confidence: float = 0.0,
    processing_time: float = 0.0
):
    """Log an email processing event"""
    global _reporter
    if _reporter:
        event = EmailEvent(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            subject=subject,
            from_address=from_address,
            action=action,
            reason=reason,
            agent_type=agent_type,
            confidence=confidence,
            processing_time=processing_time
        )
        _reporter.add_event(event)


def stop_reporter():
    """Stop the global reporter"""
    global _reporter
    if _reporter:
        _reporter.stop_reporting()
        _reporter = None


def test_reporter(report_email: str, sender_email: str):
    """Test the reporter by sending an immediate test report"""
    print(f"🧪 Testing reporter system...")
    print(f"   Sender: {sender_email}")
    print(f"   Recipient: {report_email}")
    
    # Create a temporary reporter
    test_reporter_instance = EmailReporter(report_email, sender_email)
    
    # Add a test event
    test_event = EmailEvent(
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        subject="Test Email Report",
        from_address="test@example.com",
        action="processed",
        reason="This is a test report to verify the reporting system works correctly",
        agent_type="general",
        confidence=1.0,
        processing_time=0.5
    )
    test_reporter_instance.add_event(test_event)
    
    # Send immediate report
    try:
        html_report, text_report = test_reporter_instance._generate_report()
        if html_report and text_report:
            test_reporter_instance._send_report_email(html_report, text_report)
            print("✅ Test report sent successfully!")
            return True
        else:
            print("❌ Failed to generate test report")
            return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_immediate_test_report(report_email: str, sender_email: str):
    """Send an immediate test report - convenience function"""
    return test_reporter(report_email, sender_email)

