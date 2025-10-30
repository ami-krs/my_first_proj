#!/bin/bash

# Email Agent Real-time Listener
# This script starts the email listener in the background

EMAIL="${1:-amikrsjun7@gmail.com}"
REPORT_EMAIL="${2:-ami.krs@gmail.com}"
ENABLE_REPORTING=${3:-""}
LOG_FILE="email_agent_$(date +%Y%m%d_%H%M%S).log"

if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    echo "Usage: $0 <email_account> [report_email] [reporting]"
    echo "   <email_account>   Email address to monitor (required)"
    echo "   [report_email]    Where to send summary reports (default: ami.krs@gmail.com)"
    echo "   [reporting]       If set (any value), enables summary reporting every 15 minutes"
    echo "     e.g. $0 john@gmail.com admin@work.com reporting"
    echo "     e.g. $0 john@gmail.com (no summary reports)"
    exit 0
fi

echo "🚀 Starting Email Agent Listener for: $EMAIL"
echo "📊 Reports will be sent to: $REPORT_EMAIL"
echo "📝 Log file: $LOG_FILE"
echo ""

# Check if email has credentials set up
python -c "from email_agent.auth_manager import AuthManager; import sys; \
auth = AuthManager('$EMAIL'); \
sys.exit(0 if auth.get_credentials() else 1)" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "❌ No stored credentials for $EMAIL"
    echo "Please run: python -m email_agent.runner --setup $EMAIL"
    exit 1
fi

# Start the listener in background
if [ -n "$ENABLE_REPORTING" ]; then
    python -m email_agent.listener --email "$EMAIL" --report-email "$REPORT_EMAIL" --enable-reporting >> "$LOG_FILE" 2>&1 &
else
    python -m email_agent.listener --email "$EMAIL" --report-email "$REPORT_EMAIL" >> "$LOG_FILE" 2>&1 &
fi
LISTENER_PID=$!

echo "✅ Email Agent started (PID: $LISTENER_PID)"
echo "📋 To stop: kill $LISTENER_PID"
echo "📋 To view logs: tail -f $LOG_FILE"
echo ""

# Save PID to file for easy stopping
echo $LISTENER_PID > .email_agent.pid

echo "🎧 Listening for emails..."
echo "   Press Ctrl+C to stop (or run: kill \$(cat .email_agent.pid))"

# Wait and show logs
tail -f "$LOG_FILE"

