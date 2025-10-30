from __future__ import annotations

import os
import re
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from openai import OpenAI

from .models import DraftDecision, EmailContent, MeetingDetails


@dataclass
class WebSnippet:
    """Represents a cleaned web search result snippet"""
    content: str
    source_url: Optional[str] = None
    title: Optional[str] = None
    cleaned: bool = False


@dataclass
class FactualGroundingResult:
    """Result of factual grounding validation"""
    is_grounded: bool
    confidence_score: float
    missing_facts: List[str]
    potential_hallucinations: List[str]
    validated_facts: List[str]


class WebResultPreCleaner:
    """Pre-cleans web search results to ensure only factual content is used"""
    
    def __init__(self):
        self.suspicious_patterns = [
            r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',  # IP addresses
            r'\b\d{3}-\d{3}-\d{4}\b',  # Phone numbers
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email addresses
            r'\b\d{5}(-\d{4})?\b',  # ZIP codes
            r'\$\d+',  # Dollar amounts
            r'\b(https?://[^\s]+)\b',  # URLs
        ]
        
        self.factual_indicators = [
            r'\b(according to|as reported|sources say|confirmed|verified)\b',
            r'\b(company|organization|business|corporation)\b',
            r'\b(established|founded|located at|headquarters)\b',
        ]
    
    def clean_snippet(self, snippet: str, source_url: Optional[str] = None) -> WebSnippet:
        """Clean and validate a web snippet"""
        cleaned_content = self._remove_suspicious_content(snippet)
        cleaned_content = self._extract_factual_content(cleaned_content)
        
        return WebSnippet(
            content=cleaned_content,
            source_url=source_url,
            cleaned=True
        )
    
    def _remove_suspicious_content(self, content: str) -> str:
        """Remove potentially sensitive or made-up information"""
        cleaned = content
        
        for pattern in self.suspicious_patterns:
            cleaned = re.sub(pattern, '[REDACTED]', cleaned, flags=re.IGNORECASE)
        
        return cleaned
    
    def _extract_factual_content(self, content: str) -> str:
        """Extract only factual content from the snippet"""
        sentences = content.split('. ')
        factual_sentences = []
        
        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in self.factual_indicators):
                factual_sentences.append(sentence)
            elif not any(pattern in sentence for pattern in self.suspicious_patterns):
                # Keep sentences that don't contain suspicious patterns
                factual_sentences.append(sentence)
        
        return '. '.join(factual_sentences)


class FactualGroundingValidator:
    """Validates responses against provided content to prevent hallucination"""
    
    def __init__(self):
        self.client = None
    
    def _make_client(self, api_key: Optional[str] = None) -> OpenAI:
        """Create OpenAI client"""
        if not self.client:
            key = api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("OPENAI_API_KEY not configured")
            self.client = OpenAI(api_key=key)
        return self.client
    
    def validate_response_grounding(
        self, 
        original_email: EmailContent,
        draft_response: str,
        web_snippets: Optional[List[WebSnippet]] = None,
        api_key: Optional[str] = None
    ) -> FactualGroundingResult:
        """Validate that the response is grounded in provided facts"""
        
        # Prepare source content
        source_content = self._prepare_source_content(original_email, web_snippets)
        
        # Use LLM to validate grounding
        validation_prompt = f"""
        You are a factual validation agent. Your job is to check if the draft response contains 
        any information that is NOT present in the source content provided.
        
        SOURCE CONTENT:
        {source_content}
        
        DRAFT RESPONSE:
        {draft_response}
        
        Analyze the response and return a JSON object with:
        {{
            "is_grounded": true/false,
            "confidence_score": 0.0-1.0,
            "missing_facts": ["list of facts that appear to be made up"],
            "potential_hallucinations": ["specific claims that aren't in source"],
            "validated_facts": ["facts that are properly sourced"]
        }}
        
        Rules:
        - If any address, phone number, or specific factual detail appears in the response 
          but not in the source content, mark it as a hallucination
        - Company names, addresses, and contact details must be explicitly provided in source
        - Meeting details should be based on explicit requests or provided information
        - Be strict about factual accuracy
        """
        
        client = self._make_client(api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {"role": "system", "content": "You are a strict factual validator. Return only valid JSON."},
                {"role": "user", "content": validation_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        try:
            result_data = json.loads(response.choices[0].message.content)
            return FactualGroundingResult(
                is_grounded=result_data.get("is_grounded", False),
                confidence_score=result_data.get("confidence_score", 0.0),
                missing_facts=result_data.get("missing_facts", []),
                potential_hallucinations=result_data.get("potential_hallucinations", []),
                validated_facts=result_data.get("validated_facts", [])
            )
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return FactualGroundingResult(
                is_grounded=False,
                confidence_score=0.0,
                missing_facts=["JSON parsing error"],
                potential_hallucinations=["Unable to validate"],
                validated_facts=[]
            )
    
    def _prepare_source_content(
        self, 
        email: EmailContent, 
        web_snippets: Optional[List[WebSnippet]] = None
    ) -> str:
        """Prepare source content for validation"""
        content_parts = [
            f"ORIGINAL EMAIL:",
            f"Subject: {email.subject}",
            f"From: {email.from_address}",
            f"Body: {email.plain_text}",
        ]
        
        if email.html:
            content_parts.append(f"HTML Body: {email.html}")
        
        if web_snippets:
            content_parts.append("\nWEB SEARCH RESULTS:")
            for snippet in web_snippets:
                content_parts.append(f"- {snippet.content}")
                if snippet.source_url:
                    content_parts.append(f"  Source: {snippet.source_url}")
        
        return "\n".join(content_parts)


SYSTEM_PROMPT = (
    "You are an executive assistant with strict factual grounding requirements. "
    "Read the incoming email and produce a clear reply subject and body. "
    "If the email implies scheduling, propose a meeting based on constraints and availability hints. "
    "Use concise, professional tone. "
    "\n"
    "RESPONSE BEHAVIOR RULES:"
    "\n"
    "1. PROVIDE IMMEDIATE, HELPFUL RESPONSES - Do not defer or postpone information. "
    "   If someone asks for details, provide what you can immediately rather than saying "
    "   'I'll provide this later' or 'this will be sent tomorrow'"
    "\n"
    "2. BE PROACTIVE AND ACTIONABLE - Give concrete information, suggestions, or next steps "
    "   that can be acted upon immediately"
    "\n"
    "3. OFFER TO SCHEDULE MEETINGS - If information is complex, offer to schedule a call "
    "   or meeting rather than deferring written responses"
    "\n"
    "\n"
    "CRITICAL FACTUAL GROUNDING RULES:"
    "\n"
    "1. NEVER provide specific addresses, phone numbers, or factual details unless "
    "   explicitly provided in the original email or web search results"
    "\n"
    "2. NEVER make up or hallucinate information like company addresses, contact details, "
    "   or specific business information"
    "\n"
    "3. If you need specific information that isn't provided, ask the sender to provide it "
    "   AND offer immediate alternatives (like scheduling a call to discuss)"
    "\n"
    "4. When using web search results, only reference information that is explicitly "
    "   mentioned in the provided snippets"
    "\n"
    "5. If uncertain about any factual detail, provide what you can immediately and "
    "   suggest a meeting or call to clarify specifics"
    "\n"
    "6. For meeting scheduling, only use details explicitly mentioned in the email"
)


def _make_client(api_key: Optional[str] = None) -> OpenAI:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=key)

# Global whitelist for trusted senders (lowercase)
WHITELIST = [
    "@gmail.com",  # Example domain: allow any real Gmail human
    "@outlook.com",
    # Add more trusted domains or exact emails as needed, eg: "team@company.com"
]

def is_auto_or_spam(email):
    sender = email.from_address.lower()
    subject = email.subject.lower()
    body_preview = email.plain_text.lower()

    # Always allow if on whitelist
    if any(allowed in sender for allowed in WHITELIST):
        print(f"[WHITELIST ALLOW] {sender} {subject}")
        return False

    # Rule 1: no-reply senders
    if any(keyword in sender for keyword in ["no-reply", "noreply", "do-not-reply"]):
        print(f"[SPAM SKIP] no-reply sender: {sender}, subject: {subject}")
        return True

    # Rule 2: marketing domains
    if any(domain in sender for domain in ["mailchimp", "hubspot", "substack", "medium.com", "sendgrid"]):
        print(f"[SPAM SKIP] marketing domain: {sender}, subject: {subject}")
        return True

    # Rule 3: spammy subject or system notification, but only skip if sender is not personal
    spam_words = ["unsubscribe", "offer", "deal", "discount", "newsletter", "promo", "ad:"]
    sys_words = ["password reset", "verification code", "invoice", "receipt", "auto-reply", "out of office"]
    if any(word in subject for word in spam_words + sys_words):
        # If sender looks like a real person (e.g. has a firstname.lastname@gmail.com), allow!
        if ("@gmail.com" in sender or "@outlook.com" in sender or "@yahoo.com" in sender):
            print(f"[HUMAN PASS] Possibly spammy subject, but sender looks like a human: {sender} → subject: {subject}")
            return False
        print(f"[SPAM SKIP] spam keyword in subject, system word, or out of office: {sender}, subject: {subject}")
        return True

    return False

SYSTEM_PROMPT_CLASSIFIER = """
You are an intelligent email intent classifier.
Decide if the email should be analyzed by the assistant.
Reply only with one of the following labels:
- HUMAN: Sent by a person, needs a thoughtful response.
- AUTOMATED: Newsletter, notification, promo, or no-reply.
"""

def classify_email_with_llm(subject, body):
    client = _make_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_CLASSIFIER},
            {"role": "user", "content": f"Subject: {subject}\nBody: {body[:1000]}"} # limit text length
        ]
    )
    label = response.choices[0].message.content.strip().upper()
    if label not in ["HUMAN", "AUTOMATED"]:
        print(f"[LLM WARNING] Unknown label '{label}' for subject '{subject}'. Defaulting to HUMAN.")
        return True
    if label == "AUTOMATED":
        print(f"[LLM CLASSIFIER SKIP] Email classified as AUTOMATED - Subject: {subject}")
        return False
    print(f"[LLM PASS] Email classified as HUMAN - Subject: {subject}")
    return True

SYSTEM_PROMPT_ANALYST = """
You are an email analysis and information extraction agent.
Use ONLY the provided web snippets or email content.
Never invent company addresses or facts not shown.
If you cannot find the answer, reply with: NOT_FOUND.
Return your analysis in structured JSON:
{
 "intent": "...",
 "meeting_needed": true/false,
 "key_facts": ["..."],
 "response_draft": "..."
}
"""
def fact_check_email_with_llm(subject, body):
    client = _make_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_ANALYST},
            {"role": "user", "content": f"Subject: {subject}\nBody: {body[:1000]}"} # limit text length
        ]
    )
    label = response.choices[0].message.content.strip().upper()
    return label

def analyze_and_draft(
    email: EmailContent,
    model: str = "gpt-4o-mini",
    temperature: float = 0.2,
    default_timezone: str = "UTC",
    default_meeting_duration_minutes: int = 30,
    api_key: Optional[str] = None,
    web_snippets: Optional[List[WebSnippet]] = None,
    enable_factual_validation: bool = True,
) -> DraftDecision:
    client = _make_client(api_key)

    # Prepare web snippets content if provided
    web_content = ""
    if web_snippets:
        web_content = "\n\nWEB SEARCH RESULTS (use only if explicitly relevant):\n"
        for snippet in web_snippets:
            web_content += f"- {snippet.content}\n"
            if snippet.source_url:
                web_content += f"  Source: {snippet.source_url}\n"
    
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
{web_content}

Task:
- Decide whether a meeting should be scheduled.
- If yes, provide meeting title, timezone (default {default_timezone}), duration minutes (default {default_meeting_duration_minutes}), location if specified, and list of attendees (include sender plus any explicit attendees mentioned).
- Provide a professional, concise reply body in both plain text and simple HTML (basic <p> tags), and a reply subject prefixed with 'Re:' if appropriate.
- Keep to actionable, short sentences.
- ONLY use information explicitly provided in the email or web search results above.
- CRITICAL: Provide immediate, helpful responses. Do NOT defer information to later dates or say "I'll provide this tomorrow." Instead:
  * Give what information you can immediately
  * Offer to schedule a meeting/call for complex discussions
  * Suggest immediate next steps or alternatives
  * Be proactive and actionable in your response

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

    # Perform factual validation if enabled
    if enable_factual_validation:
        draft_response = f"Subject: {data.get('reply_subject', '')}\n\nBody: {data.get('reply_body_text', '')}"
        validator = FactualGroundingValidator()
        
        try:
            validation_result = validator.validate_response_grounding(
                original_email=email,
                draft_response=draft_response,
                web_snippets=web_snippets,
                api_key=api_key
            )
            
            # Log validation results
            if not validation_result.is_grounded:
                print(f"⚠ Factual validation failed (confidence: {validation_result.confidence_score:.2f})")
                if validation_result.potential_hallucinations:
                    print(f"Potential hallucinations: {validation_result.potential_hallucinations}")
                
                # Modify response to be more conservative
                if validation_result.potential_hallucinations:
                    # Add disclaimer to response
                    original_text = data.get("reply_body_text", "")
                    disclaimer = "\n\nNote: Please provide any specific details (addresses, contact information, etc.) that you'd like me to include in our response."
                    data["reply_body_text"] = original_text + disclaimer
                    
                    if data.get("reply_body_html"):
                        original_html = data["reply_body_html"]
                        html_disclaimer = "<p><em>Note: Please provide any specific details (addresses, contact information, etc.) that you'd like me to include in our response.</em></p>"
                        data["reply_body_html"] = original_html + html_disclaimer
            else:
                print(f"✓ Factual validation passed (confidence: {validation_result.confidence_score:.2f})")
                
        except Exception as e:
            print(f"⚠ Factual validation error: {e}")
            # Continue with original response if validation fails

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


def clean_web_search_results(raw_snippets: List[str], source_urls: Optional[List[str]] = None) -> List[WebSnippet]:
    """
    Clean web search results to remove potentially fabricated information
    and ensure only factual content is used
    """
    cleaner = WebResultPreCleaner()
    cleaned_snippets = []
    
    for i, snippet in enumerate(raw_snippets):
        source_url = source_urls[i] if source_urls and i < len(source_urls) else None
        cleaned = cleaner.clean_snippet(snippet, source_url)
        cleaned_snippets.append(cleaned)
    
    return cleaned_snippets


def analyze_and_draft_with_web_search(
    email: EmailContent,
    web_search_results: Optional[List[str]] = None,
    web_source_urls: Optional[List[str]] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.2,
    default_timezone: str = "UTC",
    default_meeting_duration_minutes: int = 30,
    api_key: Optional[str] = None,
) -> DraftDecision:
    """
    Enhanced version of analyze_and_draft that includes web search result cleaning
    and factual validation
    """
    # Clean web search results if provided
    web_snippets = None
    if web_search_results:
        web_snippets = clean_web_search_results(web_search_results, web_source_urls)
        print(f"✓ Cleaned {len(web_snippets)} web search results")
    
    # Use the enhanced analyze_and_draft function
    return analyze_and_draft(
        email=email,
        model=model,
        temperature=temperature,
        default_timezone=default_timezone,
        default_meeting_duration_minutes=default_meeting_duration_minutes,
        api_key=api_key,
        web_snippets=web_snippets,
        enable_factual_validation=True,
    )
