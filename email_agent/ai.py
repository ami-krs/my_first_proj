from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from .models import DraftDecision, EmailContent, MeetingDetails


SYSTEM_PROMPT = (
    "You are an executive assistant. Read the incoming email and produce: "
    "a clear reply subject and body. If the email implies scheduling, propose a meeting "
    "based on constraints and availability hints. Use concise, professional tone. "
    "IMPORTANT: Never provide specific addresses, phone numbers, or factual details unless "
    "explicitly provided in the original email. Do not make up or hallucinate information. "
    "If you need specific information, ask the sender to provide it rather than guessing."
)


def _make_client(api_key: Optional[str] = None) -> OpenAI:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=key)


def analyze_and_draft(
    email: EmailContent,
    model: str = "gpt-4o-mini",
    temperature: float = 0.2,
    default_timezone: str = "UTC",
    default_meeting_duration_minutes: int = 30,
    api_key: Optional[str] = None,
) -> DraftDecision:
    client = _make_client(api_key)

    user_prompt = f"""
Incoming email:
Subject: {email.subject}
From: {email.from_address}
To: {', '.join(email.to_addresses)}
CC: {', '.join(email.cc_addresses)}
Date: {email.date}

Plain text body:
{email.plain_text}

HTML body (if any):
{email.html or ''}

Task:
- Decide whether a meeting should be scheduled.
- If yes, provide meeting title, timezone (default {default_timezone}), duration minutes (default {default_meeting_duration_minutes}), location if specified, and list of attendees (include sender plus any explicit attendees mentioned).
- Provide a professional, concise reply body in both plain text and simple HTML (basic <p> tags), and a reply subject prefixed with 'Re:' if appropriate.
- Keep to actionable, short sentences.
Return a strict JSON object with keys: reply_subject, reply_body_text, reply_body_html, needs_meeting (boolean), meeting (object|null with keys: title, start_datetime (ISO8601), duration_minutes, timezone, location, attendees, description).
"""

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("No content from OpenAI")

    import json
    data = json.loads(content)

    meeting: Optional[MeetingDetails] = None
    if data.get("needs_meeting") and data.get("meeting"):
        m = data["meeting"]
        from dateutil import parser as dateparser
        from zoneinfo import ZoneInfo

        # Parse and normalize meeting start datetime
        dt = dateparser.isoparse(m["start_datetime"]) if m.get("start_datetime") else None
        tz_name = m.get("timezone") or default_timezone
        if dt is not None and dt.tzinfo is None:
            try:
                dt = dt.replace(tzinfo=ZoneInfo(tz_name))
            except Exception:
                dt = dt.replace(tzinfo=ZoneInfo(default_timezone))

        meeting = MeetingDetails(
            title=m.get("title") or email.subject,
            start_datetime=dt if dt is not None else None,  # type: ignore[arg-type]
            duration_minutes=int(
                m.get("duration_minutes") or default_meeting_duration_minutes
            ),
            timezone=tz_name,
            location=m.get("location"),
            attendees=list(m.get("attendees") or [email.from_address]),
            description=m.get("description"),
        )

    return DraftDecision(
        reply_subject=data.get("reply_subject") or f"Re: {email.subject}",
        reply_body_text=data.get("reply_body_text") or "",
        reply_body_html=data.get("reply_body_html"),
        needs_meeting=bool(data.get("needs_meeting")),
        meeting=meeting,
    )
