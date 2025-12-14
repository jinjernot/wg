"""
Email Validation Diagnostic Script
Run this to check your email validation setup and troubleshoot issues.
"""

import os
import json
from pathlib import Path
from datetime import datetime

print("=" * 70)
print("EMAIL VALIDATION DIAGNOSTIC")
print("=" * 70)
print()

# Check credentials directory
creds_dir = Path("data/config/credentials")
print(f"📁 Credentials Directory: {creds_dir}")
print(f"   Exists: {'✅ Yes' if creds_dir.exists() else '❌ No'}")
print()

if creds_dir.exists():
    print("🔑 Credential Files Found:")
    creds_files = list(creds_dir.glob("credentials_*.json"))
    token_files = list(creds_dir.glob("token_*.json"))
    
    for cred in sorted(creds_files):
        name = cred.stem.replace("credentials_", "")
        token = creds_dir / f"token_{name}.json"
        
        # Check if token exists and is valid
        token_status = "❌ Missing"
        if token.exists():
            try:
                with open(token) as f:
                    token_data = json.load(f)
                    if "expiry" in token_data:
                        token_status = f"✅ Present (may need refresh)"
                    else:
                        token_status = "✅ Present"
            except:
                token_status = "⚠️ Corrupt"
        
        print(f"   • {name}")
        print(f"     Credentials: ✅ {cred.name}")
        print(f"     Token: {token_status}")
    
    # Check for orphaned tokens (token without credentials)
    orphaned = []
    for token in token_files:
        name = token.stem.replace("token_", "")
        cred = creds_dir / f"credentials_{name}.json"
        if not cred.exists():
            orphaned.append(name)
    
    if orphaned:
        print()
        print("⚠️  Orphaned Tokens (no credentials file):")
        for name in orphaned:
            print(f"   • {name}")
else:
    print("❌ Credentials directory does not exist!")
    print(f"   Expected: {creds_dir.absolute()}")

print()
print("-" * 70)
print()

# Check email logs directory
email_logs = Path("email_logs")
print(f"📧 Email Logs Directory: {email_logs}")
print(f"   Exists: {'✅ Yes' if email_logs.exists() else '❌ No (will be created on first validation)'}")
print()

if email_logs.exists():
    # Check search logs
    search_logs = email_logs / "_search_logs"
    if search_logs.exists():
        search_files = list(search_logs.glob("*.json"))
        print(f"🔍 Search Logs: {len(search_files)} file(s)")
        if search_files:
            # Show most recent
            most_recent = max(search_files, key=lambda p: p.stat().st_mtime)
            mod_time = datetime.fromtimestamp(most_recent.stat().st_mtime)
            print(f"   Most recent: {most_recent.name}")
            print(f"   Time: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Load and show summary
            try:
                with open(most_recent) as f:
                    data = json.load(f)
                print(f"   Trade: {data.get('trade_hash', 'Unknown')}")
                print(f"   Validator: {data.get('validator', 'Unknown')}")
                print(f"   Emails found: {data.get('emails_found', 0)}")
            except:
                pass
    else:
        print("🔍 Search Logs: None yet")
    
    print()
    
    # Check validator subdirectories
    validators = ["scotiabank", "banco_azteca", "oxxo"]
    for validator in validators:
        v_dir = email_logs / validator
        if v_dir.exists():
            trade_dirs = [d for d in v_dir.iterdir() if d.is_dir()]
            print(f"📨 {validator.title()}: {len(trade_dirs)} trade(s) logged")
            if trade_dirs:
                # Show most recent
                most_recent = max(trade_dirs, key=lambda p: p.stat().st_mtime)
                files = list(most_recent.glob("*"))
                print(f"   Most recent: {most_recent.name} ({len(files)} files)")

print()
print("=" * 70)
print()
print("📖 Next Steps:")
print()
print("1. Check if your credential files exist (see above)")
print("2. Make sure tokens are not expired (check error logs)")
print("3. Wait for a payment to trigger validation")
print("4. Check email_logs/_search_logs/ for search queries")
print("5. Check email_logs/<validator>/<trade_hash>/ for actual emails")
print()
print("For more info, read: email_logs/README.md")
print()
