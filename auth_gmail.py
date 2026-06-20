"""
Gmail Authentication Helper Script
Run this script to authenticate your Gmail account interactively.
It will open a browser window for you to log in and save the token.json.
"""
import sys
import os

from core.validation.email import get_gmail_service

print("=" * 60)
print("GMAIL INTERACTIVE AUTHENTICATION")
print("=" * 60)
print("This will open a browser window to authenticate with Google.")
print("Once completed, it will save the token.json in data/config/credentials.")
print()

try:
    service = get_gmail_service("default", interactive=True)
    if service:
        print("✅ Success! Gmail service authenticated successfully.")
        print("token.json has been written to data/config/credentials/token.json")
    else:
        print("❌ Authentication failed. Make sure credentials.json is valid.")
except Exception as e:
    print(f"❌ Error during authentication: {e}")
