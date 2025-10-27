"""
Router Agent - Classifies and routes emails to appropriate expert agents
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI
from .models import EmailContent


@dataclass
class RoutingDecision:
    """Decision made by the router agent"""
    agent_type: str  # "scheduling", "business", "information", "general"
    confidence: float
    reasoning: str
    requires_information: bool = False


class RouterAgent:
    """Router/Classifier Agent that intelligently routes emails to expert agents"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def classify_and_route(self, email: EmailContent) -> RoutingDecision:
        """
        Analyze email and determine which expert agent should handle it
        
        Returns:
            RoutingDecision with agent type, confidence, and reasoning
        """
        
        prompt = self._build_classification_prompt(email)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Low temperature for consistent classification
            max_tokens=500
        )
        
        return self._parse_response(response.choices[0].message.content)
    
    def _get_system_prompt(self) -> str:
        """System prompt defining the router's role"""
        return """You are a Router Agent specialized in email classification for an AI email assistant system.

Your job is to analyze incoming emails and classify them into one of these categories:

1. **SCHEDULING** - Emails that involve:
   - Meeting requests
   - Calendar events
   - Time/date coordination
   - Availability queries

2. **BUSINESS** - Emails that involve:
   - Sales inquiries
   - Customer support
   - Business negotiations
   - Partnership opportunities
   - Professional relationships

3. **INFORMATION** - Emails that need:
   - Web search for facts
   - Information retrieval
   - Research-based responses
   - Data verification

4. **GENERAL** - All other emails including:
   - General questions
   - Casual conversations
   - Thank you messages
   - Other miscellaneous content

For each email, provide:
1. Agent type: one of "scheduling", "business", "information", or "general"
2. Confidence: a float between 0.0 and 1.0
3. Reasoning: brief explanation (1-2 sentences)
4. Requires information: true/false if the email needs external information

Respond ONLY in this JSON format:
{
    "agent_type": "scheduling|business|information|general",
    "confidence": 0.95,
    "reasoning": "Brief explanation here",
    "requires_information": false
}"""
    
    def _build_classification_prompt(self, email: EmailContent) -> str:
        """Build the classification prompt from email content"""
        return f"""Analyze this email and classify it:

**Subject:** {email.subject}
**From:** {email.from_address}
**Content:**
{email.plain_text[:1000]}

Classify this email and respond in the specified JSON format."""
    
    def _parse_response(self, response_text: str) -> RoutingDecision:
        """Parse the LLM response into a RoutingDecision"""
        import json
        import re
        
        # Extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            # Fallback to default
            return RoutingDecision(
                agent_type="general",
                confidence=0.5,
                reasoning="Could not parse response",
                requires_information=False
            )
        
        try:
            data = json.loads(json_match.group())
            return RoutingDecision(
                agent_type=data.get("agent_type", "general"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                requires_information=bool(data.get("requires_information", False))
            )
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing router response: {e}")
            return RoutingDecision(
                agent_type="general",
                confidence=0.5,
                reasoning=f"Parse error: {str(e)}",
                requires_information=False
            )
