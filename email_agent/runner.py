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


def run_once() -> int:
    """Run the multi-agent email system once"""
    cfg = load_config()

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
    parser = argparse.ArgumentParser(description="Multi-Agent AI Email System - one-shot run")
    _ = parser.parse_args(argv)
    return run_once()


if __name__ == "__main__":
    sys.exit(main())
