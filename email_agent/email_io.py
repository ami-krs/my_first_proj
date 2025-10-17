from __future__ import annotations

import email
import imaplib
import smtplib
import socket
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, parsedate_to_datetime, make_msgid
from typing import Optional, Tuple

from bs4 import BeautifulSoup

from .models import EmailContent


@dataclass
class SMTPConnection:
    server: smtplib.SMTP

    def send(self, msg: EmailMessage) -> None:
        self.server.send_message(msg)

    def close(self) -> None:
        try:
            self.server.quit()
        except Exception:
            try:
                self.server.close()
            except Exception:
                pass


def _decode_mime_words(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _extract_plain_and_html(msg: email.message.Message) -> Tuple[str, Optional[str]]:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = (part.get_content_type() or "").lower()
            if part.get_content_maintype() == "multipart":
                continue
            try:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
            except Exception:
                continue

            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(text)
    else:
        content_type = (msg.get_content_type() or "").lower()
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if content_type == "text/plain":
            plain_parts.append(text)
        elif content_type == "text/html":
            html_parts.append(text)

    plain_text = "\n\n".join(plain_parts).strip()
    html = None
    if html_parts:
        soup = BeautifulSoup("\n\n".join(html_parts), "html.parser")
        # Normalize excessive whitespace
        html = str(soup)
        if not plain_text:
            plain_text = soup.get_text("\n").strip()

    return plain_text, html


def fetch_latest_unseen(
    host: str,
    port: int,
    username: str,
    password: str,
    use_ssl: bool = True,
    mailbox: str = "INBOX",
) -> Optional[EmailContent]:
    try:
        if use_ssl:
            M = imaplib.IMAP4_SSL(host, port)
        else:
            M = imaplib.IMAP4(host, port)
    except (socket.gaierror, OSError) as exc:
        raise RuntimeError(
            f"Failed to connect to IMAP server at {host}:{port}. "
            f"Please verify IMAP_HOST/IMAP_PORT and network connectivity."
        ) from exc
    try:
        M.login(username, password)
        M.select(mailbox)
        typ, data = M.search(None, "UNSEEN")
        if typ != "OK":
            return None
        ids = (data[0] or b"").split()
        if not ids:
            return None
        latest_id = ids[-1]
        typ, msg_data = M.fetch(latest_id, "(RFC822)")
        if typ != "OK":
            return None
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        subject = _decode_mime_words(msg.get("Subject"))
        from_addr = _decode_mime_words(msg.get("From"))
        to_addr = _decode_mime_words(msg.get("To"))
        cc_addr = _decode_mime_words(msg.get("Cc"))
        date_hdr = msg.get("Date")
        dt = parsedate_to_datetime(date_hdr) if date_hdr else None

        plain, html = _extract_plain_and_html(msg)

        to_addresses = [a.strip() for a in (to_addr or "").split(",") if a.strip()]
        cc_addresses = [a.strip() for a in (cc_addr or "").split(",") if a.strip()]

        return EmailContent(
            subject=subject or "",
            from_address=from_addr or "",
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            date=dt,
            plain_text=plain,
            html=html,
            message_id=msg.get("Message-ID"),
            references=msg.get("References"),
        )
    finally:
        try:
            M.logout()
        except Exception:
            pass


def connect_smtp(
    host: str,
    port: int,
    username: str,
    password: str,
    from_address: str,
    from_name: Optional[str] = None,
    use_starttls: bool = True,
    use_ssl: bool = False,
) -> SMTPConnection:
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port)
        else:
            server = smtplib.SMTP(host, port)
    except (socket.gaierror, OSError) as exc:
        raise RuntimeError(
            f"Failed to connect to SMTP server at {host}:{port}. "
            f"Please verify SMTP_HOST/SMTP_PORT and network connectivity."
        ) from exc
    server.ehlo()
    if use_starttls and not use_ssl:
        server.starttls()
        server.ehlo()
    server.login(username, password)
    return SMTPConnection(server)


def send_reply(
    smtp: SMTPConnection,
    original: EmailContent,
    subject: str,
    body_text: str,
    body_html: Optional[str],
    from_address: str,
    from_name: Optional[str] = None,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = original.from_address
    msg["From"] = (
        formataddr((from_name, from_address)) if from_name else from_address
    )
    # Reply threading headers
    if original.message_id:
        msg["In-Reply-To"] = original.message_id
        if original.references:
            msg["References"] = f"{original.references} {original.message_id}"
        else:
            msg["References"] = original.message_id

    msg["Message-ID"] = make_msgid()

    if body_html:
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")
    else:
        msg.set_content(body_text)

    smtp.send(msg)
