#!/usr/bin/env python3
"""
Test script for the Email Reporter system
Sends an immediate test report to verify the reporting system works
"""

import sys
from email_agent.reporter import test_reporter

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_reporter.py <sender_email> <report_email>")
        print("Example: python test_reporter.py amikrsjun7@gmail.com ami.krs@gmail.com")
        sys.exit(1)
    
    sender_email = sys.argv[1]
    report_email = sys.argv[2]
    
    print("="*60)
    print("🧪 Email Reporter Test")
    print("="*60)
    print()
    
    success = test_reporter(report_email, sender_email)
    
    if success:
        print()
        print("✅ Test completed! Check your inbox at", report_email)
        sys.exit(0)
    else:
        print()
        print("❌ Test failed! Check the error messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

