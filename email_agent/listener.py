"""
Real-time Email Listener using IMAP IDLE
Listens for new emails and triggers the agent automatically
"""

from __future__ import annotations
import sys
import time
import threading
from typing import Optional
import imaplib
import email
from email.header import decode_header
import signal

from .config import load_config
from .auth_manager import AuthManager
from .ai import is_auto_or_spam, classify_email_with_llm
from .review_ai import review_draft
from .calendar import build_ics, attach_ics
from .router import RouterAgent
from .experts import SchedulingAgent, BusinessAgent, InformationAgent, GeneralAgent
from .reporter import init_reporter, log_email_event, stop_reporter


class EmailListener:
    """Real-time email listener using IMAP IDLE protocol"""
    
    def __init__(self, email_account: str, poll_interval: int = 30, report_email: str = "ami.krs@gmail.com", enable_reporting: bool = False):
        """
        Initialize email listener
        
        Args:
            email_account: Email address to monitor
            poll_interval: Polling interval in seconds (fallback if IDLE not supported)
            report_email: Email address to send reports to
            enable_reporting: If True, turn on summary report emails
        """
        self.email_account = email_account
        self.poll_interval = poll_interval
        self.report_email = report_email
        self.enable_reporting = enable_reporting
        self.running = False
        self.imap = None
        self.credentials = None
        self.cfg = None
        
    def _get_credentials(self):
        """Get stored credentials"""
        auth_manager = AuthManager(self.email_account)
        creds = auth_manager.get_credentials()
        
        if not creds:
            print(f"❌ No stored credentials for {self.email_account}")
            print("Please run: python -m email_agent.runner --setup your_email@example.com")
            return False
        
        self.credentials = creds
        return True
    
    def _load_config(self):
        """Load base configuration"""
        self.cfg = load_config()
        # Override with user credentials
        class UserConfig:
            def __init__(self, orig_cfg, creds):
                self.imap = type('IMAP', (), {
                    'host': creds.imap_host,
                    'port': orig_cfg.imap.port,
                    'username': creds.username,
                    'password': creds.imap_password,
                    'use_ssl': orig_cfg.imap.use_ssl,
                    'mailbox': orig_cfg.imap.mailbox,
                })()
                self.smtp = type('SMTP', (), {
                    'host': creds.smtp_host,
                    'port': orig_cfg.smtp.port,
                    'username': creds.username,
                    'password': creds.smtp_password,
                    'from_address': creds.username,
                    'from_name': orig_cfg.smtp.from_name,
                    'use_starttls': orig_cfg.smtp.use_starttls,
                    'use_ssl': orig_cfg.smtp.use_ssl,
                })()
                self.openai = orig_cfg.openai
                self.agent = orig_cfg.agent
        
        self.cfg = UserConfig(self.cfg, self.credentials)
        return True
    
    def _connect_imap(self):
        """Connect to IMAP server"""
        try:
            if self.cfg.imap.use_ssl:
                self.imap = imaplib.IMAP4_SSL(self.cfg.imap.host, self.cfg.imap.port)
            else:
                self.imap = imaplib.IMAP4(self.cfg.imap.host, self.cfg.imap.port)
            
            self.imap.login(self.cfg.imap.username, self.cfg.imap.password)
            self.imap.select(self.cfg.imap.mailbox, readonly=True)
            
            print(f"✅ Connected to {self.cfg.imap.host}")
            return True
        except Exception as e:
            print(f"❌ IMAP connection failed: {e}")
            return False
    
    def _process_email(self, msg_id: bytes):
        """Process a single email through the multi-agent system"""
        start_time = time.time()
        
        try:
            # Fetch email
            status, data = self.imap.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                return False
            
            raw_email = data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract email details
            subject = decode_header(email_message["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()
            
            from_address = email_message["From"]
            
            # Get plain text content
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = email_message.get_payload(decode=True).decode()
            
            print(f"\n📧 New email: {subject}")
            print(f"   From: {from_address}")
            
            # Create EmailContent object
            from .models import EmailContent
            mail = EmailContent(
                subject=subject,
                from_address=from_address,
                to_addresses=[self.email_account],
                plain_text=body[:1000],  # Limit for processing
            )
            
            # Filter spam
            if is_auto_or_spam(email=mail):
                print("   Skipped: Non-human or promotional email")
                log_email_event(
                    subject=subject,
                    from_address=from_address,
                    action="skipped_spam",
                    reason="Non-human or promotional email",
                    processing_time=time.time() - start_time
                )
                return False
            
            if not classify_email_with_llm(mail.subject, mail.plain_text):
                print("   Skipped: Auto or promotional email")
                log_email_event(
                    subject=subject,
                    from_address=from_address,
                    action="skipped_auto",
                    reason="Auto or promotional email",
                    processing_time=time.time() - start_time
                )
                return False
            
            # Router Agent
            router = RouterAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
            routing_decision = router.classify_and_route(mail)
            
            print(f"\n🔀 Router: {routing_decision.agent_type.upper()} (confidence: {routing_decision.confidence:.2f})")
            
            # Expert Agent
            expert_decision = None
            agent_type = routing_decision.agent_type
            if routing_decision.agent_type == "scheduling":
                agent = SchedulingAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
                expert_decision = agent.draft_response(
                    mail,
                    default_timezone=self.cfg.agent.default_timezone,
                    default_meeting_duration_minutes=self.cfg.agent.default_meeting_duration_minutes
                )
            elif routing_decision.agent_type == "business":
                agent = BusinessAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
                expert_decision = agent.draft_response(mail)
            elif routing_decision.agent_type == "information":
                agent = InformationAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
                expert_decision = agent.draft_response(mail)
            else:
                agent = GeneralAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
                expert_decision = agent.draft_response(mail)
            
            if not expert_decision:
                log_email_event(
                    subject=subject,
                    from_address=from_address,
                    action="error",
                    reason="Expert agent failed to generate response",
                    agent_type=agent_type,
                    confidence=routing_decision.confidence,
                    processing_time=time.time() - start_time
                )
                return False
            
            # Review Agent
            review_decision = review_draft(
                original_email=mail,
                draft_decision=expert_decision,
                model=self.cfg.openai.model,
                temperature=self.cfg.openai.temperature,
                api_key=self.cfg.openai.api_key,
            )
            
            print(f"✅ Review: {'Approved' if review_decision.approved else 'Modified'}")
            
            # Send email
            from .email_io import connect_smtp
            from email.message import EmailMessage
            from email.utils import formataddr
            
            smtp = connect_smtp(
                host=self.cfg.smtp.host,
                port=self.cfg.smtp.port,
                username=self.cfg.smtp.username,
                password=self.cfg.smtp.password,
                from_address=self.cfg.smtp.from_address,
                from_name=self.cfg.smtp.from_name,
                use_starttls=self.cfg.smtp.use_starttls,
                use_ssl=self.cfg.smtp.use_ssl,
            )
            
            msg = EmailMessage()
            msg["Subject"] = review_decision.final_subject
            msg["To"] = mail.from_address
            msg["From"] = formataddr((self.cfg.smtp.from_name, self.cfg.smtp.from_address))
            
            if review_decision.final_body_html:
                msg.set_content(review_decision.final_body_text)
                msg.add_alternative(review_decision.final_body_html, subtype="html")
            else:
                msg.set_content(review_decision.final_body_text)
            
            if review_decision.final_needs_meeting and review_decision.final_meeting:
                try:
                    ics = build_ics(review_decision.final_meeting, self.cfg.smtp.from_address, self.cfg.smtp.from_name)
                    attach_ics(msg, ics)
                    print(f"   📅 Calendar invite attached")
                except Exception as e:
                    print(f"Warning: {e}")
            
            smtp.send(msg)
            smtp.close()
            
            print("✅ Email sent successfully!")
            
            # Log successful processing
            log_email_event(
                subject=subject,
                from_address=from_address,
                action="processed",
                reason="Successfully processed and replied",
                agent_type=agent_type,
                confidence=routing_decision.confidence,
                processing_time=time.time() - start_time
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing email: {e}")
            log_email_event(
                subject=subject if 'subject' in locals() else "Unknown",
                from_address=from_address if 'from_address' in locals() else "Unknown",
                action="error",
                reason=f"Processing error: {str(e)}",
                processing_time=time.time() - start_time
            )
            return False
    
    def _process_email_by_uid(self, uid):
        try:
            status, data = self.imap.uid('FETCH', str(uid), '(RFC822)')
            if status != 'OK':
                print(f"[ERROR] Could not fetch UID {uid}")
                return
            raw_email = data[0][1]
            import email
            from email.header import decode_header
            import time
            start_time = time.time()
            email_message = email.message_from_bytes(raw_email)
            # Extract email details
            subject = decode_header(email_message["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()
            from_address = email_message["From"]
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = email_message.get_payload(decode=True).decode()
            print(f"\n📧 [UID={uid}] New email: {subject}")
            print(f"   From: {from_address}")

            # Create EmailContent object
            from .models import EmailContent
            mail = EmailContent(
                subject=subject,
                from_address=from_address,
                to_addresses=[self.email_account],
                plain_text=body[:1000],
            )
            # Filtering
            if is_auto_or_spam(email=mail):
                print("   Skipped: Non-human or promotional email")
                log_email_event(
                    subject=subject,
                    from_address=from_address,
                    action="skipped_spam",
                    reason="Non-human or promotional email",
                    processing_time=time.time() - start_time
                )
                return False
            if not classify_email_with_llm(mail.subject, mail.plain_text):
                print("   Skipped: Auto or promotional email")
                log_email_event(
                    subject=subject,
                    from_address=from_address,
                    action="skipped_auto",
                    reason="Auto or promotional email",
                    processing_time=time.time() - start_time
                )
                return False
            # AGENT, REVIEW, SMTP SEND - full expert pipeline copied from _process_email
            router = RouterAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
            routing_decision = router.classify_and_route(mail)
            print(f"\n🔀 Router: {routing_decision.agent_type.upper()} (confidence: {routing_decision.confidence:.2f})")

            expert_decision = None
            agent_type = routing_decision.agent_type
            if routing_decision.agent_type == "scheduling":
                agent = SchedulingAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
                expert_decision = agent.draft_response(
                    mail,
                    default_timezone=self.cfg.agent.default_timezone,
                    default_meeting_duration_minutes=self.cfg.agent.default_meeting_duration_minutes
                )
            elif routing_decision.agent_type == "business":
                agent = BusinessAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
                expert_decision = agent.draft_response(mail)
            elif routing_decision.agent_type == "information":
                agent = InformationAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
                expert_decision = agent.draft_response(mail)
            else:
                agent = GeneralAgent(api_key=self.cfg.openai.api_key, model=self.cfg.openai.model)
                expert_decision = agent.draft_response(mail)

            if not expert_decision:
                print("❌ No expert decision made.")
                return False

            review_decision = review_draft(
                original_email=mail,
                draft_decision=expert_decision,
                model=self.cfg.openai.model,
                temperature=self.cfg.openai.temperature,
                api_key=self.cfg.openai.api_key,
            )

            print(f"✅ Review: {'Approved' if review_decision.approved else 'Modified'}")

            # Send email (SMTP)
            from .email_io import connect_smtp
            from email.message import EmailMessage
            from email.utils import formataddr
            smtp = connect_smtp(
                host=self.cfg.smtp.host,
                port=self.cfg.smtp.port,
                username=self.cfg.smtp.username,
                password=self.cfg.smtp.password,
                from_address=self.cfg.smtp.from_address,
                from_name=self.cfg.smtp.from_name,
                use_starttls=self.cfg.smtp.use_starttls,
                use_ssl=self.cfg.smtp.use_ssl,
            )
            msg = EmailMessage()
            msg["Subject"] = review_decision.final_subject
            msg["To"] = mail.from_address
            msg["From"] = formataddr((self.cfg.smtp.from_name, self.cfg.smtp.from_address))

            if review_decision.final_body_html:
                msg.set_content(review_decision.final_body_text)
                msg.add_alternative(review_decision.final_body_html, subtype="html")
            else:
                msg.set_content(review_decision.final_body_text)

            if hasattr(review_decision, 'final_needs_meeting') and review_decision.final_needs_meeting and getattr(review_decision, 'final_meeting', None):
                try:
                    ics = build_ics(review_decision.final_meeting, self.cfg.smtp.from_address, self.cfg.smtp.from_name)
                    attach_ics(msg, ics)
                    print(f"   📅 Calendar invite attached")
                except Exception as e:
                    print(f"Warning: {e}")

            smtp.send(msg)
            smtp.close()

            print("✅ Email sent successfully!")
            return True
        except Exception as ex:
            print(f"[EXCEPTION in _process_email_by_uid] UID {uid}: {ex}")
            return False
    
    def _listen_idle(self):
        """UID-based real time idle listener loop."""
        while self.running:
            try:
                self.imap.noop()
                status, messages = self.imap.uid('SEARCH', None, f'UID {self.max_uid+1}:* UNSEEN')
                if status == 'OK':
                    email_uids = [int(uid) for uid in messages[0].split()]
                    for uid in email_uids:
                        if uid in self.processed_uids:
                            print(f"[INFO] Already processed UID {uid}, skipping.")
                            continue
                        self.processed_uids.add(uid)
                        print(f"🔔 Detected new email, UID={uid}")
                        self._process_email_by_uid(uid)
                        if uid > self.max_uid:
                            self.max_uid = uid  # Advance UID baseline
                time.sleep(self.poll_interval)
            except imaplib.IMAP4.error as e:
                print(f"❌ IMAP error: {e}")
                print("Reconnecting...")
                self._connect_imap()
            except Exception as ex:
                print(f"[UNEXPECTED ERROR] {ex}")
    
    def start(self):
        """Start the email listener"""
        print("\n" + "="*60)
        print("🚀 Email Agent - Real-time Listener")
        print("="*60 + "\n")
        
        if not self._get_credentials():
            return False
        
        if not self._load_config():
            return False
        
        if not self._connect_imap():
            return False
        
        if self.enable_reporting:
            # Initialize reporting system
            print(f"📊 Initializing reporting system...")
            print(f"   Reports will be sent to: {self.report_email}")
            print(f"   Report frequency: Every 15 minutes")
            init_reporter(self.report_email, self.email_account)
            
            # Send initial test report to verify system works
            print(f"   Sending initial test report...")
            from .reporter import test_reporter
            try:
                test_reporter(self.report_email, self.email_account)
                print(f"   ✅ Initial test report sent successfully!")
            except Exception as e:
                print(f"   ⚠️  Initial test report failed: {e}")
                print(f"   Reporting will continue - next report in 15 minutes")
        else:
            print("📊 Summary report generation is DISABLED.")
        
        self.running = True
        
        # Find the highest UID at startup to anchor to real-time mode
        print("🔑 Determining highest existing UID at agent startup...")
        self.imap.select(self.cfg.imap.mailbox, readonly=True)
        typ, data = self.imap.uid('SEARCH', None, 'ALL')
        all_uids = data[0].split()
        if all_uids:
            self.max_uid = int(all_uids[-1])
            print(f"Last UID in inbox at startup: {self.max_uid}")
        else:
            self.max_uid = 0
            print("✅ Inbox empty at startup")
        self.processed_uids = set()

        # Setup signal handler for graceful shutdown
        def signal_handler(sig, frame):
            print("\n\n👋 Shutting down...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start listening
        try:
            self._listen_idle()
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """Stop the listener"""
        self.running = False
        if self.imap:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass
        stop_reporter()
        print("✅ Listener stopped")


def main():
    """Main entry point for the listener"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time Email Listener")
    parser.add_argument('--email', '-e', required=True, help='Email address to monitor')
    parser.add_argument('--poll-interval', '-p', type=int, default=30, help='Polling interval in seconds')
    parser.add_argument('--report-email', '-r', default='ami.krs@gmail.com', help='Email address to send reports to')
    parser.add_argument('--enable-reporting', action='store_true', help='Enable 15-min summary report emails')
    
    args = parser.parse_args()
    
    listener = EmailListener(args.email, args.poll_interval, args.report_email, args.enable_reporting)
    listener.start()


if __name__ == "__main__":
    main()

