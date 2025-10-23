from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from .models import DraftDecision, EmailContent, ReviewDecision


REVIEW_SYSTEM_PROMPT = (
    "You are a senior executive assistant with 15+ years of experience reviewing and improving email communications. "
    "Your role is to create high-quality, contextually appropriate email responses that: "
    "1. Directly address the specific requests and concerns in the original email "
    "2. Maintain professional tone while being personable and engaging "
    "3. Provide clear, actionable information and next steps "
    "4. Include specific details, deadlines, and concrete commitments where appropriate "
    "5. Ensure meeting details are complete with specific times, locations, and agendas "
    "6. Anticipate follow-up questions and address them proactively "
    "7. Use the executive's voice - confident, helpful, and solution-oriented "
    "8. Avoid generic responses - make each email feel personalized and thoughtful "
    "9. NEVER provide specific addresses, phone numbers, or factual details unless explicitly provided in the original email "
    "10. NEVER make up or hallucinate information - only work with what's provided "
    "11. If you need specific information, ask the sender to provide it rather than guessing "
    "12. Focus on being helpful without providing potentially incorrect factual information "
    "13. CRITICAL: Provide IMMEDIATE, helpful responses. Do NOT defer information to later dates, "
    "    say 'I'll provide this tomorrow,' or postpone responses. Instead: "
    "    * Give what information you can immediately "
    "    * Offer to schedule meetings/calls for complex discussions "
    "    * Suggest immediate next steps or alternatives "
    "    * Be proactive and actionable rather than deferring "
    "When improving drafts, rewrite them completely rather than just suggesting changes. "
    "Focus on substance, clarity, and professional relationship building while maintaining accuracy."
)


def _make_client(api_key: Optional[str] = None) -> OpenAI:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=key)


def _analyze_email_context(email: EmailContent) -> dict:
    """Analyze email content to provide context for better responses."""
    content = email.plain_text.lower()
    subject = email.subject.lower()
    
    # Determine email type
    email_type = "general"
    if any(word in content for word in ["meeting", "schedule", "call", "discuss"]):
        email_type = "meeting_request"
    elif any(word in content for word in ["urgent", "asap", "immediately", "emergency"]):
        email_type = "urgent_request"
    elif any(word in content for word in ["question", "help", "advice", "guidance"]):
        email_type = "inquiry"
    elif any(word in content for word in ["proposal", "project", "collaboration"]):
        email_type = "business_proposal"
    elif any(word in content for word in ["thank", "appreciate", "grateful"]):
        email_type = "appreciation"
    
    # Extract key requests
    key_requests = []
    if "meeting" in content or "schedule" in content:
        key_requests.append("meeting_scheduling")
    if "quote" in content or "price" in content or "cost" in content:
        key_requests.append("pricing_inquiry")
    if "information" in content or "details" in content:
        key_requests.append("information_request")
    if "deadline" in content or "timeline" in content:
        key_requests.append("timeline_inquiry")
    
    # Determine urgency
    urgency = "normal"
    if any(word in content for word in ["urgent", "asap", "immediately", "emergency", "critical"]):
        urgency = "high"
    elif any(word in content for word in ["when convenient", "no rush", "whenever"]):
        urgency = "low"
    
    # Determine relationship
    relationship = "professional"
    if any(word in content for word in ["hi", "hello", "thanks", "appreciate"]):
        relationship = "friendly_professional"
    if any(word in content for word in ["dear", "sir", "madam", "formal"]):
        relationship = "formal"
    
    # Extract action items
    action_items = []
    if "floor plan" in content:
        action_items.append("provide_floor_plan")
    if "quote" in content:
        action_items.append("provide_quote")
    if "meeting" in content:
        action_items.append("schedule_meeting")
    if "poem" in content:
        action_items.append("create_poem")
    
    return {
        "email_type": email_type,
        "key_requests": ", ".join(key_requests) if key_requests else "general_inquiry",
        "urgency": urgency,
        "relationship": relationship,
        "action_items": ", ".join(action_items) if action_items else "general_response"
    }


def review_draft(
    original_email: EmailContent,
    draft_decision: DraftDecision,
    model: str = "gpt-4o",
    temperature: float = 0.3,
    api_key: Optional[str] = None,
) -> ReviewDecision:
    client = _make_client(api_key)

    user_prompt = f"""
ORIGINAL EMAIL TO RESPOND TO:
Subject: {original_email.subject}
From: {original_email.from_address}
To: {', '.join(original_email.to_addresses)}
CC: {', '.join(original_email.cc_addresses)}
Date: {original_email.date}

Content:
{original_email.plain_text}

DRAFT REPLY TO IMPROVE:
Subject: {draft_decision.reply_subject}
Body: {draft_decision.reply_body_text}
Meeting needed: {draft_decision.needs_meeting}
Meeting details: {draft_decision.meeting}

TASK: Create a high-quality, contextually appropriate response that:
1. Directly addresses what the sender is asking for
2. Provides specific, actionable information
3. Shows understanding of their needs and concerns
4. Maintains professional yet personable tone
5. Includes concrete next steps and timelines
6. Anticipates and addresses potential follow-up questions

CRITICAL RULES - MUST FOLLOW:
- ONLY use information explicitly provided in the original email
- NEVER make up specific facts, dates, addresses, phone numbers, or details
- NEVER provide information about external events, timelines, or reports unless mentioned in the original email
- If you need specific information, ask the sender to provide it
- Focus on being helpful and professional without fabricating details
- Use phrases like "I'd be happy to help with that" or "Let me know more details about..." instead of making assumptions
- Keep responses general and helpful rather than specific and potentially incorrect

IMPORTANT: 
- Rewrite the entire response to be more specific and helpful
- Don't just suggest changes - provide the complete improved version
- Make it feel like a thoughtful, personalized response from a senior executive
- Include specific details, deadlines, and commitments where appropriate
- If a meeting is needed, provide complete details with specific time, location, and agenda
- NEVER include specific addresses, phone numbers, or factual details that weren't in the original email
- If you need specific information, ask the sender to provide it rather than making assumptions
- Focus on being helpful without providing potentially incorrect information

Return JSON with:
- approved (boolean): true if original draft is excellent, false if improvement needed
- suggested_changes (string|null): brief explanation of improvements made, null if approved
- final_subject (string): improved subject line
- final_body_text (string): complete improved plain text response
- final_body_html (string|null): improved HTML version (or null)
- final_needs_meeting (boolean): whether meeting is needed
- final_meeting (object|null): complete meeting details if needed
"""

    # Add context analysis for better responses
    context_analysis = _analyze_email_context(original_email)
    
    enhanced_prompt = f"""
{user_prompt}

CONTEXT ANALYSIS:
- Email type: {context_analysis['email_type']}
- Key requests: {context_analysis['key_requests']}
- Urgency level: {context_analysis['urgency']}
- Relationship: {context_analysis['relationship']}
- Action items: {context_analysis['action_items']}

Use this context to create a highly relevant and specific response.
"""

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": enhanced_prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("No content from OpenAI review")

    import json
    data = json.loads(content)

    # Parse meeting details if present
    final_meeting = None
    if data.get("final_needs_meeting") and data.get("final_meeting"):
        m = data["final_meeting"]
        from dateutil import parser as dateparser
        from zoneinfo import ZoneInfo

        # Parse and normalize meeting start datetime
        dt = dateparser.isoparse(m["start_datetime"]) if m.get("start_datetime") else None
        tz_name = m.get("timezone") or "UTC"
        if dt is not None and dt.tzinfo is None:
            try:
                dt = dt.replace(tzinfo=ZoneInfo(tz_name))
            except Exception:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        from .models import MeetingDetails
        final_meeting = MeetingDetails(
            title=m.get("title") or original_email.subject,
            start_datetime=dt if dt is not None else None,
            duration_minutes=int(m.get("duration_minutes") or 30),
            timezone=tz_name,
            location=m.get("location"),
            attendees=list(m.get("attendees") or [original_email.from_address]),
            description=m.get("description"),
        )

    return ReviewDecision(
        approved=bool(data.get("approved")),
        suggested_changes=data.get("suggested_changes"),
        final_subject=data.get("final_subject") or draft_decision.reply_subject,
        final_body_text=data.get("final_body_text") or draft_decision.reply_body_text,
        final_body_html=data.get("final_body_html"),
        final_needs_meeting=bool(data.get("final_needs_meeting")),
        final_meeting=final_meeting,
    )
