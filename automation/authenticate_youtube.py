#!/usr/bin/env python3
"""
Run this ONCE to authenticate with YouTube.
After this, token is saved and future uploads work automatically.
"""

import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(SCRIPT_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "youtube_token.pickle")

def authenticate():
    print("=" * 50)
    print("YOUTUBE AUTHENTICATION")
    print("=" * 50)

    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"\nERROR: {CLIENT_SECRETS_FILE} not found!")
        print("Download it from Google Cloud Console and place in this folder.")
        return False

    print("\n1. Opening browser for Google sign-in...")
    print("2. Sign in with your Google account")
    print("3. Click 'Allow' to grant YouTube upload permission")
    print("4. Browser will show 'Authentication successful'")
    print("5. Come back to this terminal\n")

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=8080)

    # Save token
    with open(TOKEN_FILE, 'wb') as token:
        pickle.dump(credentials, token)

    print("=" * 50)
    print("AUTHENTICATION SUCCESSFUL!")
    print(f"Token saved to: {TOKEN_FILE}")
    print("You can now upload videos to YouTube.")
    print("=" * 50)

    return True

if __name__ == "__main__":
    authenticate()