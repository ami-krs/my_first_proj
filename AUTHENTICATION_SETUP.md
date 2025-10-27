# 🔐 Authentication Setup Guide

## Overview

This guide will help you set up secure authentication for your multi-agent email system.

## 📋 Prerequisites

1. **Python with keyring installed**
   ```bash
   pip install keyring
   ```

2. **Email account with app password enabled**
   - Gmail: Enable 2FA and create app password
   - Outlook: Generate app password
   - Other providers: Check their app password documentation

## 🚀 Step-by-Step Setup

### Step 1: Enter Your Email

When you run the setup, you'll be prompted for:

```bash
python -m email_agent.runner --setup your_email@example.com
```

**Example:**
```bash
python -m email_agent.runner --setup user@gmail.com
```

### Step 2: Provide IMAP Configuration

You'll be asked for:
- **IMAP Server**: `imap.gmail.com` (default for Gmail)
- **IMAP Password**: Your app password (not regular password)

Example responses:
```
IMAP Server (default: imap.gmail.com): imap.gmail.com
IMAP Password (app password): xxxx xxxx xxxx xxxx
```

### Step 3: Provide SMTP Configuration

You'll be asked for:
- **SMTP Server**: `smtp.gmail.com` (default for Gmail)
- **SMTP Password**: Your app password (same as above)

Example responses:
```
SMTP Server (default: smtp.gmail.com): smtp.gmail.com
SMTP Password (app password): xxxx xxxx xxxx xxxx
```

### Step 4: Save Credentials

```
💾 Save credentials for future use? (Y/n): Y
```

Press Enter to save (or type `Y` and press Enter).

### Step 5: Verification

You should see:
```
✅ Credentials saved for your_email@example.com
```

## 📧 Gmail Setup (Most Common)

### Get Gmail App Password

1. Go to https://myaccount.google.com/
2. Click **Security** in the left sidebar
3. Enable **2-Step Verification** (if not already enabled)
4. Search for "App passwords" in the top search bar
5. Select **App** and **Device** (e.g., Mail, Other)
6. Click **Generate**
7. Copy the 16-character password (shown like: xxxx xxxx xxxx xxxx)

### Use the App Password

When prompted during setup, enter this app password (not your regular Gmail password).

## 🎯 Different Email Providers

### Outlook/Office 365

**IMAP Settings:**
- Server: `outlook.office365.com`
- Port: 993 (SSL)

**SMTP Settings:**
- Server: `smtp.office365.com`
- Port: 587 (STARTTLS)

**App Password:**
- Go to https://account.microsoft.com/security
- Click **Security** > **Advanced security options**
- Click **Create a new app password**

### Yahoo

**IMAP Settings:**
- Server: `imap.mail.yahoo.com`
- Port: 993 (SSL)

**SMTP Settings:**
- Server: `smtp.mail.yahoo.com`
- Port: 587 (STARTTLS)

**App Password:**
- Go to https://login.yahoo.com/account/security
- Click **Generate an app password**

### Custom Email Provider

Check with your provider for:
- IMAP server hostname
- SMTP server hostname
- Port numbers
- Security settings (SSL/TLS)
- App password generation

## 🔒 Security Best Practices

### ✅ Do's

- Use app passwords (not regular passwords)
- Enable 2-factor authentication
- Keep app passwords private
- Use different app passwords for different apps
- Rotate app passwords periodically

### ❌ Don'ts

- Don't use your main email password
- Don't share your app password
- Don't commit credentials to Git
- Don't store passwords in plain text files

## 🛠️ Managing Credentials

### View Stored Credentials

Credentials are stored in your system's keyring. On macOS, you can view them in Keychain Access:

```bash
open /Applications/Utilities/Keychain\ Access.app
```

Search for "AI Email Agent" to find stored credentials.

### Delete Credentials

To remove stored credentials:

```bash
python -m email_agent.runner --delete your_email@example.com
```

### Update Credentials

To update stored credentials:

```bash
python -m email_agent.runner --setup your_email@example.com
```

This will prompt you to overwrite existing credentials.

## 🧪 Testing

After setup, test your credentials:

```bash
python -m email_agent.runner --email your_email@example.com
```

This will:
1. Retrieve stored credentials
2. Connect to your email
3. Process the latest email
4. Send a response

## 🎯 Next Steps

Once setup is complete, you can:

1. **Run interactively:**
   ```bash
   python -m email_agent.runner
   ```

2. **Use specific email:**
   ```bash
   python -m email_agent.runner --email your_email@example.com
   ```

3. **Silent mode (no prompts):**
   ```bash
   python -m email_agent.runner --email your_email@example.com --use-stored
   ```

## 📝 Examples

### Example 1: Gmail Setup

```bash
$ python -m email_agent.runner --setup user@gmail.com

🔐 Email Authentication Setup
============================================================

Setting up credentials for: user@gmail.com

--- IMAP Configuration ---
IMAP Server (default: imap.gmail.com): [Enter]
IMAP Password (app password): xxxx xxxx xxxx xxxx

--- SMTP Configuration ---
SMTP Server (default: smtp.gmail.com): [Enter]
SMTP Password (app password): xxxx xxxx xxxx xxxx

💾 Save credentials for future use? (Y/n): [Enter]
✅ Credentials saved for user@gmail.com
```

### Example 2: Running the Agent

```bash
$ python -m email_agent.runner --email user@gmail.com

📧 Processing email: Hello
   From: someone@example.com

🔀 Router Decision:
   Agent Type: GENERAL
   Confidence: 0.85

📝 General Agent drafting response...

🔍 Review Agent reviewing draft...

✅ Review Complete:
   ✓ Draft approved by review agent

✅ Email sent successfully!
```

## ❓ Troubleshooting

### "IMAP error: Authentication failed"

**Problem:** Wrong password or app password not used.

**Solution:**
1. Verify you're using an app password (not regular password)
2. Regenerate the app password
3. Re-run setup

### "keyring import error"

**Problem:** Keyring library not installed.

**Solution:**
```bash
pip install keyring
```

### "No stored credentials"

**Problem:** Credentials not saved during setup.

**Solution:**
Run setup again and make sure to save when prompted.

## ✅ Success!

Once setup is complete, you can now:
- Process emails automatically
- Use multiple email accounts
- Switch between accounts easily
- Run without entering passwords

Happy emailing! 🚀

