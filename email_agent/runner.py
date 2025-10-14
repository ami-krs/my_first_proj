from __future__ import annotations

import argparse
import sys
from typing import Optional

from .config import load_config
from .email_io import fetch_latest_unseen, connect_smtp, send_reply
from .ai import analyze_and_draft
from .calendar import build_ics, attach_ics


def run_once() -> int:
    cfg = load_config()

    mail = fetch_latest_unseen(
        host=cfg.imap.host,
        port=cfg.imap.port,
        username=cfg.imap.username,
        password=cfg.imap.password,
        use_ssl=cfg.imap.use_ssl,
        mailbox=cfg.imap.mailbox,
    )

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
    try:
        # Build email
        from email.message import EmailMessage
        from email.utils import formataddr

        msg = EmailMessage()
        msg["Subject"] = decision.reply_subject
        msg["To"] = mail.from_address
        msg["From"] = (
            formataddr((cfg.smtp.from_name, cfg.smtp.from_address))
            if cfg.smtp.from_name
            else cfg.smtp.from_address
        )
        if mail.message_id:
            msg["In-Reply-To"] = mail.message_id
            if mail.references:
                msg["References"] = f"{mail.references} {mail.message_id}"
            else:
                msg["References"] = mail.message_id

        if decision.reply_body_html:
            msg.set_content(decision.reply_body_text)
            msg.add_alternative(decision.reply_body_html, subtype="html")
        else:
            msg.set_content(decision.reply_body_text)

        # Attach calendar invite if needed
        if decision.needs_meeting and decision.meeting:
            ics = build_ics(decision.meeting, cfg.smtp.from_address, cfg.smtp.from_name)
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
