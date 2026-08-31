#!/usr/bin/env python3
"""
YouTube OAuth Re-Authentication Script
Run this to generate a fresh youtube_token.pickle
"""

import os
import sys
import pickle
import base64

# Add current directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("Installing required packages...")
    os.system("pip install google-auth google-auth-oauthlib google-auth-httplib2")
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CLIENT_SECRETS_FILE = os.path.join(SCRIPT_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "youtube_token.pickle")

def main():
    print("=" * 60)
    print("YouTube OAuth Re-Authentication")
    print("=" * 60)
    
    # Check if client_secret.json exists
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"\nERROR: {CLIENT_SECRETS_FILE} not found!")
        print("\nTo get this file:")
        print("1. Go to https://console.cloud.google.com")
        print("2. Select your project")
        print("3. Go to APIs & Services > Credentials")
        print("4. Find your OAuth 2.0 Client ID")
        print("5. Click Download to get client_secret.json")
        print(f"6. Place it in: {SCRIPT_DIR}")
        return False
    
    # Remove old token if it exists
    if os.path.exists(TOKEN_FILE):
        print(f"\nRemoving old token: {TOKEN_FILE}")
        os.remove(TOKEN_FILE)
    
    print("\nStarting OAuth flow...")
    print("A browser window will open. Sign in with your YouTube account.")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        credentials = flow.run_local_server(port=8090)
        
        # Save the new token
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
        
        print(f"\nSUCCESS! Token saved to: {TOKEN_FILE}")
        
        # Generate base64 for GitHub secrets
        with open(TOKEN_FILE, 'rb') as f:
            token_b64 = base64.b64encode(f.read()).decode()
        
        with open(CLIENT_SECRETS_FILE, 'rb') as f:
            secret_b64 = base64.b64encode(f.read()).decode()
        
        print("\n" + "=" * 60)
        print("GitHub Secrets (copy these):")
        print("=" * 60)
        print(f"\nYOUTUBE_TOKEN_BASE64:\n{token_b64}\n")
        print(f"\nYOUTUBE_CLIENT_SECRET_BASE64:\n{secret_b64}\n")
        
        # Save to files for easy copying
        with open("github_token_base64.txt", "w") as f:
            f.write(token_b64)
        with open("github_secret_base64.txt", "w") as f:
            f.write(secret_b64)
        
        print("Also saved to: github_token_base64.txt and github_secret_base64.txt")
        
        return True
        
    except Exception as e:
        print(f"\nERROR: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\nNext steps:")
        print("1. Go to your GitHub repo: https://github.com/imthi92/cat-podcast-voice-gen")
        print("2. Go to Settings > Secrets and variables > Actions")
        print("3. Update YOUTUBE_TOKEN_BASE64 with the new value")
        print("4. Update YOUTUBE_CLIENT_SECRET_BASE64 with the new value")
        print("5. Trigger a new workflow run")
    sys.exit(0 if success else 1)
