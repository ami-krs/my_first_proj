"""
Secure Authentication Manager for Email Agent
Uses keyring for secure credential storage
"""

import keyring
import getpass
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class EmailCredentials:
    """Stores email account credentials securely"""
    username: str
    imap_password: str
    smtp_password: str
    imap_host: str
    smtp_host: str


class AuthManager:
    """Manages secure credential storage and retrieval"""
    
    SERVICE_NAME = "AI Email Agent"
    
    def __init__(self, email_account: str):
        self.email_account = email_account
    
    def store_credentials(self, credentials: EmailCredentials, force_update: bool = False) -> bool:
        """
        Store credentials securely in system keyring
        
        Args:
            credentials: EmailCredentials object
            force_update: If True, update even if credentials exist
            
        Returns:
            True if successful
        """
        try:
            # Check if credentials already exist
            if not force_update and self.get_credentials():
                return False
            
            # Store IMAP credentials
            keyring.set_password(
                self.SERVICE_NAME,
                f"{self.email_account}_imap_password",
                credentials.imap_password
            )
            keyring.set_password(
                self.SERVICE_NAME,
                f"{self.email_account}_imap_host",
                credentials.imap_host
            )
            
            # Store SMTP credentials
            keyring.set_password(
                self.SERVICE_NAME,
                f"{self.email_account}_smtp_password",
                credentials.smtp_password
            )
            keyring.set_password(
                self.SERVICE_NAME,
                f"{self.email_account}_smtp_host",
                credentials.smtp_host
            )
            
            return True
        except Exception as e:
            print(f"Error storing credentials: {e}")
            return False
    
    def get_credentials(self) -> Optional[EmailCredentials]:
        """Retrieve stored credentials"""
        try:
            imap_password = keyring.get_password(
                self.SERVICE_NAME,
                f"{self.email_account}_imap_password"
            )
            imap_host = keyring.get_password(
                self.SERVICE_NAME,
                f"{self.email_account}_imap_host"
            )
            smtp_password = keyring.get_password(
                self.SERVICE_NAME,
                f"{self.email_account}_smtp_password"
            )
            smtp_host = keyring.get_password(
                self.SERVICE_NAME,
                f"{self.email_account}_smtp_host"
            )
            
            if all([imap_password, smtp_password, imap_host, smtp_host]):
                return EmailCredentials(
                    username=self.email_account,
                    imap_password=imap_password,
                    smtp_password=smtp_password,
                    imap_host=imap_host or "imap.gmail.com",
                    smtp_host=smtp_host or "smtp.gmail.com"
                )
        except Exception as e:
            print(f"Error retrieving credentials: {e}")
        
        return None
    
    def delete_credentials(self) -> bool:
        """Delete stored credentials"""
        try:
            keyring.delete_password(self.SERVICE_NAME, f"{self.email_account}_imap_password")
            keyring.delete_password(self.SERVICE_NAME, f"{self.email_account}_imap_host")
            keyring.delete_password(self.SERVICE_NAME, f"{self.email_account}_smtp_password")
            keyring.delete_password(self.SERVICE_NAME, f"{self.email_account}_smtp_host")
            return True
        except Exception as e:
            print(f"Error deleting credentials: {e}")
            return False
    
    @staticmethod
    def interactive_setup(email_account: str) -> Optional[EmailCredentials]:
        """
        Interactive setup for first-time authentication
        
        Returns:
            EmailCredentials if successful
        """
        print("\n" + "="*60)
        print("🔐 Email Authentication Setup")
        print("="*60)
        print(f"\nSetting up credentials for: {email_account}\n")
        
        # Get IMAP credentials
        print("--- IMAP Configuration ---")
        imap_host = input(f"IMAP Server (default: imap.gmail.com): ").strip() or "imap.gmail.com"
        imap_password = getpass.getpass("IMAP Password (app password): ").strip()
        
        # Get SMTP credentials
        print("\n--- SMTP Configuration ---")
        smtp_host = input(f"SMTP Server (default: smtp.gmail.com): ").strip() or "smtp.gmail.com"
        smtp_password = getpass.getpass("SMTP Password (app password): ").strip()
        
        if not imap_password or not smtp_password:
            print("❌ Passwords cannot be empty")
            return None
        
        credentials = EmailCredentials(
            username=email_account,
            imap_password=imap_password,
            smtp_password=smtp_password,
            imap_host=imap_host,
            smtp_host=smtp_host
        )
        
        return credentials


def get_user_email_and_credentials() -> Optional[Dict]:
    """
    Get email credentials interactively or from storage
    
    Returns:
        Dictionary with all email configuration
    """
    # Get email account from user
    email_account = input("\n📧 Enter your email address: ").strip()
    
    if not email_account:
        print("❌ Email address is required")
        return None
    
    # Try to get credentials from keyring
    auth_manager = AuthManager(email_account)
    stored_creds = auth_manager.get_credentials()
    
    if stored_creds:
        print(f"✅ Found stored credentials for {email_account}")
        use_stored = input("Use stored credentials? (Y/n): ").strip().lower()
        
        if use_stored != 'n':
            return {
                'email_account': email_account,
                'credentials': stored_creds
            }
    
    # Interactive setup
    print("\n📝 Setting up new credentials...")
    credentials = AuthManager.interactive_setup(email_account)
    
    if credentials:
        # Save credentials
        save = input("\n💾 Save credentials for future use? (Y/n): ").strip().lower()
        if save != 'n':
            auth_manager.store_credentials(credentials)
            print("✅ Credentials saved securely!")
        
        return {
            'email_account': email_account,
            'credentials': credentials
        }
    
    return None

