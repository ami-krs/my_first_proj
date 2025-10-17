from __future__ import annotations

from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Iterable, Optional

from icalendar import Calendar, Event, vCalAddress, vText
from uuid import uuid4

from .models import MeetingDetails


def build_ics(meeting: MeetingDetails, organizer_email: str, organizer_name: Optional[str] = None) -> bytes:
    cal = Calendar()
    cal.add('prodid', '-//AI Email Agent//EN')
    cal.add('version', '2.0')
    cal.add('method', 'REQUEST')

    event = Event()
    event.add('uid', str(uuid4()))
    event.add('summary', meeting.title)

    # DTSTART and DTEND should be timezone-aware; icalendar handles tzinfo on datetime
    if meeting.start_datetime is None:
        raise ValueError("Meeting start_datetime is required to build ICS")
    start_dt: datetime = meeting.start_datetime
    end_dt: datetime = start_dt + timedelta(minutes=meeting.duration_minutes)
    event.add('dtstart', start_dt)
    event.add('dtend', end_dt)

    if meeting.location:
        event.add('location', vText(meeting.location))

    if meeting.description:
        event.add('description', vText(meeting.description))

    # Organizer
    org = vCalAddress(f"MAILTO:{organizer_email}")
    if organizer_name:
        org.params['CN'] = vText(organizer_name)
    event['organizer'] = org

    # Attendees
    for attendee in meeting.attendees:
        att = vCalAddress(f"MAILTO:{attendee}")
        att.params['ROLE'] = vText('REQ-PARTICIPANT')
        event.add('attendee', att, encode=0)

    cal.add_component(event)

    return cal.to_ical()


def attach_ics(msg: EmailMessage, ics_bytes: bytes, filename: str = 'invite.ics') -> None:
    msg.add_attachment(
        ics_bytes,
        maintype='text',
        subtype='calendar',
        filename=filename,
        params={'method': 'REQUEST'}
    )
