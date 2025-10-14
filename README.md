# Email AI Agent

An AI-powered email assistant that:

- Fetches the latest unseen email via IMAP
- Uses OpenAI to analyze and draft a professional reply
- Sends the reply via SMTP
- Optionally schedules a meeting and attaches an ICS calendar invite

## Setup

Create a `.env` file with:

```
IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_USERNAME=you@example.com
IMAP_PASSWORD=your_imap_password
IMAP_SSL=true
IMAP_MAILBOX=INBOX

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=you@example.com
SMTP_PASSWORD=your_smtp_password
SMTP_STARTTLS=true
SMTP_SSL=false
FROM_ADDRESS=you@example.com
FROM_NAME=Your Name

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.2

AGENT_DEFAULT_TZ=UTC
AGENT_MEETING_DEFAULT_DURATION_MINUTES=30
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run once to process the newest unseen email and reply:

```bash
python -m email_agent.runner
```

Schedule via cron or a job runner for periodic execution.
