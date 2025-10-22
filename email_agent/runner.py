from __future__ import annotations

import argparse
import sys
from typing import Optional

from .config import load_config
from .email_io import fetch_latest_unseen, connect_smtp, send_reply
from .ai import analyze_and_draft
from .review_ai import review_draft
from .calendar import build_ics, attach_ics


def run_once() -> int:
    cfg = load_config()

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

    decision = analyze_and_draft(
        email=mail,
        model=cfg.openai.model,
        temperature=cfg.openai.temperature,
        default_timezone=cfg.agent.default_timezone,
        default_meeting_duration_minutes=cfg.agent.default_meeting_duration_minutes,
        api_key=cfg.openai.api_key,
    )

    # Review the draft with a second AI agent
    review_decision = review_draft(
        original_email=mail,
        draft_decision=decision,
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
    if review_decision.approved:
        print("✓ Draft approved by review agent")
    else:
        print("⚠ Draft modified by review agent")
        if review_decision.suggested_changes:
            print(f"Suggested changes: {review_decision.suggested_changes}")

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
            ics = build_ics(final_meeting, cfg.smtp.from_address, cfg.smtp.from_name)
            attach_ics(msg, ics)

        smtp.send(msg)
    finally:
        smtp.close()

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AI email agent - one-shot run")
    _ = parser.parse_args(argv)
    return run_once()


if __name__ == "__main__":
    sys.exit(main())
