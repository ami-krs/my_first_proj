from __future__ import annotations

import argparse
import sys
from typing import Optional

from .config import load_config
from .email_io import fetch_latest_unseen, connect_smtp, send_reply
from .ai import is_auto_or_spam, classify_email_with_llm
from .review_ai import review_draft
from .calendar import build_ics, attach_ics
from .router import RouterAgent, RoutingDecision
from .experts import SchedulingAgent, BusinessAgent, InformationAgent, GeneralAgent
from .auth_manager import AuthManager, get_user_email_and_credentials


def run_once(
    sender_email: Optional[str] = None,
    receiver_email: Optional[str] = None,
    use_stored: bool = False
) -> int:
    """
    Run the multi-agent email system once
    
    Args:
        sender_email: Email to send from (if not provided, user will be prompted)
        receiver_email: Email to send to (if not provided, will reply to received email)
        use_stored: Use stored credentials without prompting
    """
    # Step 0: Get user credentials
    if not sender_email:
        user_config = get_user_email_and_credentials()
        if not user_config:
            print("❌ Authentication failed")
            return 1
        
        sender_email = user_config['email_account']
        credentials = user_config['credentials']
        
        # Update config with user credentials
        # Note: This would need to be passed to fetch_latest_unseen
    else:
        # Use provided email and get stored credentials
        auth_manager = AuthManager(sender_email)
        stored_creds = auth_manager.get_credentials()
        
        if not stored_creds:
            print(f"❌ No stored credentials for {sender_email}")
            print("Please run setup first")
            return 1
        
        credentials = stored_creds
    
    cfg = load_config()
    
    # Override config with user credentials
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
    
    cfg = UserConfig(cfg, credentials)

    # Step 1: Fetch email
    try:
        mail = fetch_latest_unseen(
            host=cfg.imap.host,
            port=cfg.imap.port,
            username=cfg.imap.username,
            password=cfg.imap.password,
            use_ssl=cfg.imap.use_ssl,
            mailbox=cfg.imap.mailbox,
        )
    except Exception as exc:
        print(f"IMAP error: {exc}")
        return 1

    if not mail:
        return 0
    
    # Step 2: Filter spam/auto emails
    if is_auto_or_spam(email=mail):
        print("Skipped non-human or promotional email.")
        return 0

    if not classify_email_with_llm(mail.subject, mail.plain_text):
        print("Skipped auto or promotional email.")
        return 0

    print(f"📧 Processing email: {mail.subject}")
    print(f"   From: {mail.from_address}")
    
    # Step 3: Router Agent - Classify and route
    router = RouterAgent(api_key=cfg.openai.api_key, model=cfg.openai.model)
    routing_decision = router.classify_and_route(mail)
    
    print(f"\n🔀 Router Decision:")
    print(f"   Agent Type: {routing_decision.agent_type.upper()}")
    print(f"   Confidence: {routing_decision.confidence:.2f}")
    print(f"   Reasoning: {routing_decision.reasoning}")
    
    # Step 4: Expert Agent - Draft response based on routing
    expert_decision = None
    
    if routing_decision.agent_type == "scheduling":
        print(f"\n📅 Scheduling Agent drafting response...")
        scheduling_agent = SchedulingAgent(api_key=cfg.openai.api_key, model=cfg.openai.model)
        expert_decision = scheduling_agent.draft_response(
            mail, 
            default_timezone=cfg.agent.default_timezone,
            default_meeting_duration_minutes=cfg.agent.default_meeting_duration_minutes
        )
    
    elif routing_decision.agent_type == "business":
        print(f"\n💼 Business Agent drafting response...")
        business_agent = BusinessAgent(api_key=cfg.openai.api_key, model=cfg.openai.model)
        expert_decision = business_agent.draft_response(mail)
    
    elif routing_decision.agent_type == "information":
        print(f"\n🔍 Information Agent drafting response...")
        information_agent = InformationAgent(api_key=cfg.openai.api_key, model=cfg.openai.model)
        expert_decision = information_agent.draft_response(mail)
    
    else:  # general
        print(f"\n📝 General Agent drafting response...")
        general_agent = GeneralAgent(api_key=cfg.openai.api_key, model=cfg.openai.model)
        expert_decision = general_agent.draft_response(mail)
    
    if not expert_decision:
        print("❌ Error: Expert agent failed to draft response")
        return 1
    
    # Step 5: Review Agent - Review and approve
    print(f"\n🔍 Review Agent reviewing draft...")
    review_decision = review_draft(
        original_email=mail,
        draft_decision=expert_decision,
        model=cfg.openai.model,
        temperature=cfg.openai.temperature,
        api_key=cfg.openai.api_key,
    )

    # Use the reviewed decision for sending
    final_subject = review_decision.final_subject
    final_body_text = review_decision.final_body_text
    final_body_html = review_decision.final_body_html
    final_needs_meeting = review_decision.final_needs_meeting
    final_meeting = review_decision.final_meeting

    # Log review results
    print(f"\n✅ Review Complete:")
    if review_decision.approved:
        print("   ✓ Draft approved by review agent")
    else:
        print("   ⚠ Draft modified by review agent")
        if review_decision.suggested_changes:
            print(f"   Suggested changes: {review_decision.suggested_changes}")

    # Step 6: Send email
    try:
        smtp = connect_smtp(
            host=cfg.smtp.host,
            port=cfg.smtp.port,
            username=cfg.smtp.username,
            password=cfg.smtp.password,
            from_address=cfg.smtp.from_address,
            from_name=cfg.smtp.from_name,
            use_starttls=cfg.smtp.use_starttls,
            use_ssl=cfg.smtp.use_ssl,
        )
    except Exception as exc:
        print(f"SMTP error: {exc}")
        return 1
    
    try:
        # Build email
        from email.message import EmailMessage
        from email.utils import formataddr

        msg = EmailMessage()
        msg["Subject"] = final_subject
        msg["To"] = mail.from_address
        msg["From"] = (
            formataddr((cfg.smtp.from_name, cfg.smtp.from_address))
            if cfg.smtp.from_name
            else cfg.smtp.from_address
        )
        
        def _sanitize_header_value(value: str) -> str:
            # Collapse CR/LF and excessive whitespace to a single space
            return " ".join((value or "").replace("\r", "").splitlines()).strip()

        if mail.message_id:
            in_reply_to = _sanitize_header_value(mail.message_id)
            msg["In-Reply-To"] = in_reply_to
            if mail.references:
                combined_refs = f"{mail.references} {mail.message_id}"
                msg["References"] = _sanitize_header_value(combined_refs)
            else:
                msg["References"] = in_reply_to

        if final_body_html:
            msg.set_content(final_body_text)
            msg.add_alternative(final_body_html, subtype="html")
        else:
            msg.set_content(final_body_text)

        # Attach calendar invite if needed
        if final_needs_meeting and final_meeting:
            try:
                ics = build_ics(final_meeting, cfg.smtp.from_address, cfg.smtp.from_name)
                attach_ics(msg, ics)
                print(f"   📅 Calendar invite attached")
            except Exception as e:
                print(f"Warning: Could not create calendar invite: {e}")

        smtp.send(msg)
        print(f"\n✅ Email sent successfully!")
        
    finally:
        smtp.close()

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Multi-Agent AI Email System with Secure Authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for email and credentials)
  python -m email_agent.runner
  
  # Use specific email with stored credentials
  python -m email_agent.runner --email user@example.com
  
  # Setup credentials for an email
  python -m email_agent.runner --setup user@example.com
  
  # Delete stored credentials
  python -m email_agent.runner --delete user@example.com
        """
    )
    
    parser.add_argument(
        '--email', '-e',
        type=str,
        help='Email address to use (will use stored credentials)'
    )
    parser.add_argument(
        '--receiver', '-r',
        type=str,
        help='Specific receiver email (default: replies to received email)'
    )
    parser.add_argument(
        '--setup', '-s',
        type=str,
        help='Setup credentials for an email address'
    )
    parser.add_argument(
        '--delete', '-d',
        type=str,
        help='Delete stored credentials for an email address'
    )
    parser.add_argument(
        '--use-stored',
        action='store_true',
        help='Use stored credentials without prompting'
    )
    
    args = parser.parse_args(argv)
    
    # Handle setup
    if args.setup:
        from .auth_manager import AuthManager
        auth_mgr = AuthManager(args.setup)
        credentials = AuthManager.interactive_setup(args.setup)
        if credentials:
            auth_mgr.store_credentials(credentials, force_update=True)
            print(f"✅ Credentials saved for {args.setup}")
        return 0
    
    # Handle delete
    if args.delete:
        from .auth_manager import AuthManager
        auth_mgr = AuthManager(args.delete)
        if auth_mgr.delete_credentials():
            print(f"✅ Deleted credentials for {args.delete}")
        else:
            print(f"❌ No credentials found for {args.delete}")
        return 0
    
    # Run normally
    return run_once(
        sender_email=args.email,
        receiver_email=args.receiver,
        use_stored=args.use_stored
    )


if __name__ == "__main__":
    sys.exit(main())
