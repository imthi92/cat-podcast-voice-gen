#!/usr/bin/env python3
"""
Setup GitHub Secrets for Daily Automation
Run this once to prepare secrets for GitHub Actions.
"""

import base64
import os

SECRETS_DIR = os.path.join(os.path.dirname(__file__), "github_secrets")
os.makedirs(SECRETS_DIR, exist_ok=True)

print("=" * 60)
print("GITHUB SECRETS SETUP")
print("=" * 60)

# Encode youtube_token.pickle
token_path = os.path.join(os.path.dirname(__file__), "youtube_token.pickle")
if os.path.exists(token_path):
    with open(token_path, 'rb') as f:
        token_b64 = base64.b64encode(f.read()).decode()
    
    secret_file = os.path.join(SECRETS_DIR, "YOUTUBE_TOKEN_BASE64.txt")
    with open(secret_file, 'w') as f:
        f.write(token_b64)
    
    print(f"\n[YOUTUBE_TOKEN_BASE64]")
    print(f"Saved to: {secret_file}")
    print(f"Copy this value to GitHub repo → Settings → Secrets → Actions")
else:
    print(f"\nWARNING: {token_path} not found!")
    print("Run authenticate_youtube.py first.")

# Encode client_secret.json
client_path = os.path.join(os.path.dirname(__file__), "client_secret.json")
if os.path.exists(client_path):
    with open(client_path, 'r') as f:
        client_b64 = base64.b64encode(f.read().encode()).decode()
    
    secret_file = os.path.join(SECRETS_DIR, "YOUTUBE_CLIENT_SECRET_BASE64.txt")
    with open(secret_file, 'w') as f:
        f.write(client_b64)
    
    print(f"\n[YOUTUBE_CLIENT_SECRET_BASE64]")
    print(f"Saved to: {secret_file}")
    print(f"Copy this value to GitHub repo → Settings → Secrets → Actions")
else:
    print(f"\nWARNING: {client_path} not found!")

print("\n" + "=" * 60)
print("NEXT STEPS:")
print("1. Go to your GitHub repo → Settings → Secrets and variables → Actions")
print("2. Click 'New repository secret'")
print("3. Add YOUTUBE_TOKEN_BASE64 with value from github_secrets/YOUTUBE_TOKEN_BASE64.txt")
print("4. Add YOUTUBE_CLIENT_SECRET_BASE64 with value from github_secrets/YOUTUBE_CLIENT_SECRET_BASE64.txt")
print("5. The workflow will run daily at 10 AM UTC")
print("=" * 60)
