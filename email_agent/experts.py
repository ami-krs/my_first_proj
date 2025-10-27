"""
Expert Agents - Specialized agents for different types of email tasks
"""

from __future__ import annotations
from typing import Optional
from openai import OpenAI
from .models import EmailContent, DraftDecision, MeetingDetails
from datetime import datetime, timedelta
import re


class SchedulingAgent:
    """Expert agent specializing in scheduling and calendar coordination"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def draft_response(self, email: EmailContent, default_timezone: str, 
                      default_duration_minutes: int) -> DraftDecision:
        """
        Draft a response focused on scheduling and meeting coordination
        """
        
        prompt = self._build_scheduling_prompt(email, default_timezone, default_duration_minutes)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        return self._parse_response(response.choices[0].message.content, email)
    
    def _get_system_prompt(self) -> str:
        """System prompt for scheduling agent"""
        return """You are a Scheduling Agent, an expert in calendar coordination and meeting management.

Your specialties:
- Proposing meeting times based on availability
- Suggesting alternative times when conflicts occur
- Creating calendar invites with proper ICS attachments
- Coordinating across time zones
- Negotiating meeting durations and formats (in-person, video, phone)

When crafting responses:
1. Be proactive with time suggestions
2. Consider time zones carefully
3. Offer 2-3 alternative times when possible
4. Confirm meeting format and location
5. Be concise but friendly

IMPORTANT: Format your response as JSON:
{
    "subject": "Re: [original subject]",
    "body_text": "Plain text version...",
    "body_html": "<html>HTML version...</html>",
    "needs_meeting": true/false,
    "meeting": {
        "title": "Meeting Title",
        "start_time": "2024-01-15 14:00",
        "duration_minutes": 30,
        "timezone": "America/New_York",
        "location": "Zoom/In-person address",
        "description": "Meeting description"
    }
}"""
    
    def _build_scheduling_prompt(self, email: EmailContent, timezone: str, duration: int) -> str:
        """Build the scheduling prompt"""
        return f"""Draft a professional scheduling response to this email:

From: {email.from_address}
Subject: {email.subject}
Body: {email.plain_text}

Default timezone: {timezone}
Default meeting duration: {duration} minutes

Analyze the email for:
1. Meeting time preferences mentioned
2. Time zone considerations
3. Meeting format (in-person, video, phone)
4. Location requirements

Draft an appropriate scheduling response with a calendar invite if needed."""
    
    def _parse_response(self, response_text: str, email: EmailContent) -> DraftDecision:
        """Parse the scheduling agent's response"""
        import json
        import re
        
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            # Fallback to basic response
            return DraftDecision(
                reply_subject=f"Re: {email.subject}",
                reply_body_text="Thank you for your email. Let me check my availability and get back to you with some time options.",
                reply_body_html=None,
                needs_meeting=False,
                meeting=None
            )
        
        try:
            data = json.loads(json_match.group())
            
            meeting = None
            if data.get("needs_meeting") and data.get("meeting"):
                m_data = data["meeting"]
                meeting = MeetingDetails(
                    title=m_data.get("title", "Meeting"),
                    start_datetime=datetime.fromisoformat(m_data["start_time"]),
                    duration_minutes=m_data.get("duration_minutes", 30),
                    timezone=m_data.get("timezone", "UTC"),
                    location=m_data.get("location"),
                    description=m_data.get("description")
                )
            
            return DraftDecision(
                reply_subject=data.get("subject", f"Re: {email.subject}"),
                reply_body_text=data.get("body_text", ""),
                reply_body_html=data.get("body_html"),
                needs_meeting=bool(data.get("needs_meeting", False)),
                meeting=meeting
            )
        except Exception as e:
            print(f"Error parsing scheduling agent response: {e}")
            return DraftDecision(
                reply_subject=f"Re: {email.subject}",
                reply_body_text="Thank you for your email regarding scheduling. Let me check my availability.",
                reply_body_html=None,
                needs_meeting=False,
                meeting=None
            )


class BusinessAgent:
    """Expert agent specializing in business communications and sales"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def draft_response(self, email: EmailContent) -> DraftDecision:
        """Draft a professional business-focused response"""
        
        prompt = self._build_business_prompt(email)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        return self._parse_response(response.choices[0].message.content, email)
    
    def _get_system_prompt(self) -> str:
        """System prompt for business agent"""
        return """You are a Business Agent, an expert in professional business communications.

Your specialties:
- Sales inquiries and proposals
- Customer support and issue resolution
- Business negotiations
- Partnership opportunities
- Professional relationship management

Communication style:
- Professional yet personable
- Solution-oriented
- Clear and concise
- Follow-up oriented

Format your response as JSON:
{
    "subject": "Re: [original subject]",
    "body_text": "Professional response text...",
    "body_html": "<html>HTML version...</html>",
    "needs_meeting": true/false,
    "meeting": null or meeting details
}"""
    
    def _build_business_prompt(self, email: EmailContent) -> str:
        """Build the business prompt"""
        return f"""Draft a professional business response to this email:

From: {email.from_address}
Subject: {email.subject}
Body: {email.plain_text}

Consider:
1. Is this a sales inquiry, support request, or partnership opportunity?
2. What information or next steps are needed?
3. Should we schedule a meeting to discuss further?

Draft an appropriate professional response."""
    
    def _parse_response(self, response_text: str, email: EmailContent) -> DraftDecision:
        """Parse the business agent's response"""
        import json
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            return DraftDecision(
                reply_subject=f"Re: {email.subject}",
                reply_body_text="Thank you for reaching out. We appreciate your inquiry and will follow up soon.",
                reply_body_html=None,
                needs_meeting=False,
                meeting=None
            )
        
        try:
            data = json.loads(json_match.group())
            
            return DraftDecision(
                reply_subject=data.get("subject", f"Re: {email.subject}"),
                reply_body_text=data.get("body_text", ""),
                reply_body_html=data.get("body_html"),
                needs_meeting=bool(data.get("needs_meeting", False)),
                meeting=None  # Business agent typically doesn't schedule meetings immediately
            )
        except Exception as e:
            print(f"Error parsing business agent response: {e}")
            return DraftDecision(
                reply_subject=f"Re: {email.subject}",
                reply_body_text="Thank you for your business inquiry. We will review and respond promptly.",
                reply_body_html=None,
                needs_meeting=False,
                meeting=None
            )


class InformationAgent:
    """Expert agent specializing in information retrieval and research"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def draft_response(self, email: EmailContent) -> DraftDecision:
        """Draft a response with information retrieval capabilities"""
        
        prompt = self._build_information_prompt(email)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000  # More tokens for information-heavy responses
        )
        
        return self._parse_response(response.choices[0].message.content, email)
    
    def _get_system_prompt(self) -> str:
        """System prompt for information agent"""
        return """You are an Information Agent, an expert in research and information retrieval.

Your specialties:
- Answering factual questions
- Providing detailed explanations
- Researching topics and presenting findings
- Data verification and fact-checking
- Educational content delivery

Communication style:
- Informative and detailed
- Well-structured with clear points
- Accurate and verifiable information
- Proper citations when possible

Format your response as JSON:
{
    "subject": "Re: [original subject]",
    "body_text": "Information-rich response...",
    "body_html": "<html>HTML version...</html>",
    "needs_meeting": false,
    "meeting": null
}"""
    
    def _build_information_prompt(self, email: EmailContent) -> str:
        """Build the information prompt"""
        return f"""Draft an informative response to this email:

From: {email.from_address}
Subject: {email.subject}
Body: {email.plain_text}

Analyze the email for:
1. What information is being requested?
2. What level of detail is needed?
3. Are there any follow-up questions to anticipate?

Provide a comprehensive, accurate response with clear structure."""
    
    def _parse_response(self, response_text: str, email: EmailContent) -> DraftDecision:
        """Parse the information agent's response"""
        import json
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            return DraftDecision(
                reply_subject=f"Re: {email.subject}",
                reply_body_text="Thank you for your question. Let me research this and provide you with accurate information.",
                reply_body_html=None,
                needs_meeting=False,
                meeting=None
            )
        
        try:
            data = json.loads(json_match.group())
            
            return DraftDecision(
                reply_subject=data.get("subject", f"Re: {email.subject}"),
                reply_body_text=data.get("body_text", ""),
                reply_body_html=data.get("body_html"),
                needs_meeting=False,
                meeting=None
            )
        except Exception as e:
            print(f"Error parsing information agent response: {e}")
            return DraftDecision(
                reply_subject=f"Re: {email.subject}",
                reply_body_text="Thank you for your question. I'm researching this and will provide a detailed response.",
                reply_body_html=None,
                needs_meeting=False,
                meeting=None
            )


class GeneralAgent:
    """General purpose agent for miscellaneous emails"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def draft_response(self, email: EmailContent) -> DraftDecision:
        """Draft a general response"""
        
        prompt = f"""Draft a polite, professional response to this email:

From: {email.from_address}
Subject: {email.subject}
Body: {email.plain_text}

Keep the tone friendly and appropriate for the context."""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful email assistant. Draft professional, polite responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        
        return DraftDecision(
            reply_subject=f"Re: {email.subject}",
            reply_body_text=content,
            reply_body_html=None,
            needs_meeting=False,
            meeting=None
        )
