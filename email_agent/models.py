from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class EmailContent:
    subject: str
    from_address: str
    to_addresses: List[str]
    cc_addresses: List[str] = field(default_factory=list)
    date: Optional[datetime] = None
    plain_text: str = ""
    html: Optional[str] = None
    message_id: Optional[str] = None
    references: Optional[str] = None


@dataclass
class MeetingDetails:
    title: str
    start_datetime: datetime
    duration_minutes: int
    timezone: str
    location: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class DraftDecision:
    reply_subject: str
    reply_body_text: str
    reply_body_html: Optional[str]
    needs_meeting: bool
    meeting: Optional[MeetingDetails]


@dataclass
class ReviewDecision:
    approved: bool
    suggested_changes: Optional[str]
    final_subject: str
    final_body_text: str
    final_body_html: Optional[str]
    final_needs_meeting: bool
    final_meeting: Optional[MeetingDetails] = None
