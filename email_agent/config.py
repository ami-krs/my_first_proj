from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


@dataclass
class IMAPConfig:
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    mailbox: str = "INBOX"


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    from_address: str
    from_name: Optional[str] = None
    use_starttls: bool = True
    use_ssl: bool = False


@dataclass
class OpenAIConfig:
    api_key: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.2


@dataclass
class AgentConfig:
    default_timezone: str = "UTC"
    default_meeting_duration_minutes: int = 30


@dataclass
class AppConfig:
    imap: IMAPConfig
    smtp: SMTPConfig
    openai: OpenAIConfig
    agent: AgentConfig


def load_config() -> AppConfig:
    load_dotenv()

    # Required
    imap_host = os.getenv("IMAP_HOST")
    imap_user = os.getenv("IMAP_USERNAME")
    imap_pass = os.getenv("IMAP_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    from_address = os.getenv("FROM_ADDRESS")
    openai_key = os.getenv("OPENAI_API_KEY")

    missing = [
        ("IMAP_HOST", imap_host),
        ("IMAP_USERNAME", imap_user),
        ("IMAP_PASSWORD", imap_pass),
        ("SMTP_HOST", smtp_host),
        ("SMTP_USERNAME", smtp_user),
        ("SMTP_PASSWORD", smtp_pass),
        ("FROM_ADDRESS", from_address),
        ("OPENAI_API_KEY", openai_key),
    ]
    missing_names = [name for name, value in missing if not value]
    if missing_names:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing_names)}"
        )

    imap_cfg = IMAPConfig(
        host=imap_host,
        port=_get_int("IMAP_PORT", 993),
        username=imap_user,
        password=imap_pass,
        use_ssl=_get_bool("IMAP_SSL", True),
        mailbox=os.getenv("IMAP_MAILBOX", "INBOX"),
    )

    smtp_cfg = SMTPConfig(
        host=smtp_host,
        port=_get_int("SMTP_PORT", 587),
        username=smtp_user,
        password=smtp_pass,
        from_address=from_address,
        from_name=os.getenv("FROM_NAME"),
        use_starttls=_get_bool("SMTP_STARTTLS", True),
        use_ssl=_get_bool("SMTP_SSL", False),
    )

    openai_cfg = OpenAIConfig(
        api_key=openai_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
    )

    agent_cfg = AgentConfig(
        default_timezone=os.getenv("AGENT_DEFAULT_TZ", "UTC"),
        default_meeting_duration_minutes=_get_int(
            "AGENT_MEETING_DEFAULT_DURATION_MINUTES", 30
        ),
    )

    return AppConfig(
        imap=imap_cfg,
        smtp=smtp_cfg,
        openai=openai_cfg,
        agent=agent_cfg,
    )
