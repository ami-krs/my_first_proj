# 🔐 Multi-Agent Email System - Usage Guide

## Overview

This enhanced version supports secure credential storage and flexible email configuration.

## 🚀 Quick Start

### 1. Install Keyring (for secure credential storage)

```bash
pip install keyring
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

### 2. Setup Credentials (One-Time)

```bash
python -m email_agent.runner --setup your_email@example.com
```

You'll be prompted for:
- IMAP server (default: imap.gmail.com)
- IMAP password/app password
- SMTP server (default: smtp.gmail.com)  
- SMTP password/app password

Credentials are stored securely using your system's keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service).

### 3. Run the Email Agent

**Interactive Mode:**
```bash
python -m email_agent.runner
```
Prompts you to select which email account to use.

**Direct Mode:**
```bash
python -m email_agent.runner --email your_email@example.com
```
Uses stored credentials for the specified email.

**Silent Mode (no prompts):**
```bash
python -m email_agent.runner --email your_email@example.com --use-stored
```

## 📋 Available Commands

### Setup Credentials
```bash
python -m email_agent.runner --setup user@example.com
```
Sets up and stores credentials for an email address.

### Delete Credentials
```bash
python -m email_agent.runner --delete user@example.com
```
Removes stored credentials for an email address.

### Run with Specific Email
```bash
python -m email_agent.runner --email user@example.com
```

### Run with Custom Receiver
```bash
python -m email_agent.runner --receiver to@example.com
```

## 🔄 Workflow Examples

### Example 1: First-Time Setup

1. **Setup credentials:**
   ```bash
   python -m email_agent.runner --setup user@example.com
   ```

2. **Answer prompts:**
   - IMAP Server: `imap.gmail.com`
   - IMAP Password: (your app password)
   - SMTP Server: `smtp.gmail.com`
   - SMTP Password: (your app password)

3. **Save credentials?** Type `Y`

4. **Now you can run:**
   ```bash
   python -m email_agent.runner --email user@example.com
   ```

### Example 2: Multiple Email Accounts

```bash
# Setup first account
python -m email_agent.runner --setup personal@gmail.com

# Setup second account
python -m email_agent.runner --setup work@company.com

# Use specific account
python -m email_agent.runner --email personal@gmail.com
```

### Example 3: Test Different Email Accounts

```bash
# Test with account 1
python -m email_agent.runner --email account1@gmail.com

# Test with account 2
python -m email_agent.runner --email account2@gmail.com
```

## 🔒 Security Features

### Keyring Storage

Credentials are stored using your system's secure keyring:
- **macOS**: Keychain Access
- **Windows**: Windows Credential Manager
- **Linux**: Secret Service (GNOME Keyring/KWallet)

### Benefits

✅ **One-time setup** - Enter credentials once, use forever  
✅ **Secure storage** - Uses OS credential manager  
✅ **No plaintext passwords** - Encrypted by keyring  
✅ **Multiple accounts** - Easy switching between emails  

## 📧 How It Works

1. **Fetch Email**: Retrieves latest unseen email via IMAP
2. **Filter Spam**: Removes auto-replies and promotional emails
3. **Route**: Router Agent classifies and routes email
4. **Expert Processing**: Appropriate expert agent drafts response
5. **Review**: Review Agent ensures quality and safety
6. **Send**: Email sent via SMTP with optional calendar invite

## 🛠️ Troubleshooting

### "No stored credentials"

**Problem:** Email has no stored credentials.

**Solution:**
```bash
python -m email_agent.runner --setup your_email@example.com
```

### "Keyring not found"

**Problem:** Keyring library not installed.

**Solution:**
```bash
pip install keyring
```

### Wrong Credentials

**Problem:** Passwords changed or incorrect.

**Solution:**
```bash
# Delete old credentials
python -m email_agent.runner --delete your_email@example.com

# Setup again
python -m email_agent.runner --setup your_email@example.com
```

## 📊 Multi-Agent Architecture

```
Email → Router → Expert Agent → Review → Send
```

- **Router Agent**: Classifies email type
- **Scheduling Agent**: Meetings and calendar
- **Business Agent**: Professional communications
- **Information Agent**: Research and facts
- **General Agent**: Miscellaneous emails
- **Review Agent**: Quality assurance

## 🎯 Advanced Usage

### Cron Job Integration

```bash
# Run every 5 minutes
*/5 * * * * cd /path/to/project && python -m email_agent.runner --email your@email.com --use-stored
```

### Docker Usage

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "email_agent.runner", "--email", "your@email.com", "--use-stored"]
```

## 📝 Notes

- Uses app passwords for Gmail (not regular password)
- Credentials persist across sessions
- Supports multiple email accounts
- Works with any IMAP/SMTP provider
- No `.env` file needed (uses keyring)

