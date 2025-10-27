# Multi-Agent AI Email System 🚀

An intelligent, multi-agent AI-powered email assistant that uses specialized agents to handle different types of emails with expert-level precision.

## 🏗️ Architecture Overview

This system uses a **Router + Expert Agents + Reviewer** architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                      Email Processing Flow                    │
└─────────────────────────────────────────────────────────────┘

📧 Email Input
    ↓
🔀 Router Agent (Classifies email type)
    ↓
    ├──📅 Scheduling Agent (Meetings, calendar coordination)
    ├──💼 Business Agent (Sales, support, partnerships)
    ├──🔍 Information Agent (Research, factual responses)
    └──📝 General Agent (Miscellaneous emails)
    ↓
🔍 Review Agent (Quality assurance)
    ↓
📤 Send Response
```

## 🤖 Agent Roles

### 🔀 Router Agent (Classifier)
- **Purpose**: Classifies incoming emails into categories
- **Decision**: Routes to the most appropriate expert agent
- **Categories**: Scheduling, Business, Information, General
- **Confidence**: Provides confidence score for routing decision

### 📅 Scheduling Agent
- **Specialization**: Calendar coordination and meeting management
- **Capabilities**:
  - Proposes meeting times
  - Handles timezone conversions
  - Creates calendar invites (ICS attachments)
  - Suggests alternative times
  - Negotiates meeting formats

### 💼 Business Agent
- **Specialization**: Professional business communications
- **Capabilities**:
  - Sales inquiries and proposals
  - Customer support
  - Business negotiations
  - Partnership opportunities
  - Professional relationship management

### 🔍 Information Agent
- **Specialization**: Research and information retrieval
- **Capabilities**:
  - Factual question answering
  - Detailed explanations
  - Research and fact-checking
  - Educational content delivery
  - Data verification

### 📝 General Agent
- **Specialization**: Miscellaneous emails
- **Capabilities**:
  - Casual conversations
  - Thank you messages
  - General questions
  - Fallback for unclassified emails

### 🔍 Review Agent
- **Purpose**: Quality assurance and safety
- **Capabilities**:
  - Reviews drafted responses
  - Fact-checks information
  - Ensures tone and professionalism
  - Approves or suggests modifications

## 🚀 Setup

Create a `.env` file with:

```env
# IMAP Configuration
IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_USERNAME=you@example.com
IMAP_PASSWORD=your_imap_password
IMAP_SSL=true
IMAP_MAILBOX=INBOX

# SMTP Configuration
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=you@example.com
SMTP_PASSWORD=your_smtp_password
SMTP_STARTTLS=true
SMTP_SSL=false
FROM_ADDRESS=you@example.com
FROM_NAME=Your Name

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.7

# Agent Configuration
AGENT_DEFAULT_TZ=America/New_York
AGENT_MEETING_DEFAULT_DURATION_MINUTES=30
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 📖 Usage

Run once to process the newest unseen email:

```bash
python -m email_agent.runner
```

### Example Output

```
📧 Processing email: Meeting Request
   From: client@example.com

🔀 Router Decision:
   Agent Type: SCHEDULING
   Confidence: 0.95
   Reasoning: Email contains meeting request with specific time preferences

📅 Scheduling Agent drafting response...

🔍 Review Agent reviewing draft...

✅ Review Complete:
   ✓ Draft approved by review agent
   📅 Calendar invite attached

✅ Email sent successfully!
```

## 🎯 How It Works

1. **Fetch Email**: Retrieves latest unseen email via IMAP
2. **Filter Spam**: Removes auto-replies and promotional emails
3. **Route**: Router Agent classifies and routes email
4. **Expert Processing**: Appropriate expert agent drafts response
5. **Review**: Review Agent ensures quality and safety
6. **Send**: Email sent via SMTP with optional calendar invite

## 🔄 Workflow Example

**Scheduling Email:**
- Router → Scheduling Agent → Proposes meeting times → Creates ICS invite → Review → Send

**Business Inquiry:**
- Router → Business Agent → Professional response → Review → Send

**Information Request:**
- Router → Information Agent → Research & facts → Review → Send

## 🛠️ Configuration

### Customizing Agent Behavior

Each agent can be customized by modifying system prompts in:
- `email_agent/router.py` - Router classification logic
- `email_agent/experts.py` - Expert agent behaviors
- `email_agent/review_ai.py` - Review criteria

### Adding New Expert Agents

1. Create new agent class in `experts.py`
2. Update Router Agent classification in `router.py`
3. Add routing logic in `runner.py`

## 📊 Benefits of Multi-Agent Architecture

✅ **Specialization**: Each agent is expert in its domain  
✅ **Accuracy**: Better handling of specific email types  
✅ **Quality**: Multi-level review ensures high standards  
✅ **Flexibility**: Easy to add new expert agents  
✅ **Transparency**: Clear routing decisions and confidence scores  

## 🚦 Monitoring

The system provides detailed logging:
- Router decisions and confidence
- Which expert agent handled the email
- Review results and modifications
- Calendar invite creation

## 🔒 Safety & Review

Every response is reviewed by the Review Agent which:
- Checks accuracy and factual grounding
- Ensures appropriate tone
- Flags potential issues
- Provides modification suggestions

## 📝 Notes

- Schedule via cron or job runner for continuous email processing
- Each agent uses GPT-4 for optimal performance
- Calendar invites are ICS-formatted for broad compatibility
- All agents maintain conversation context with Reply-To headers
