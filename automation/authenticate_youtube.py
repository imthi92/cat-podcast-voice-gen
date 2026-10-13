#!/usr/bin/env python3
"""
YouTube Authentication — works on headless servers (Deepnote) and local machines.
Run this ONCE. After that, token is saved and uploads work automatically.
"""

import os
import sys
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Full 'youtube' scope is required so the token can also manage playlists
# (the uploader adds episodes to "The Simba Show" playlist). Using only
# 'youtube.upload' causes a 403 on playlist operations.
SCOPES = ["https://www.googleapis.com/auth/youtube"]
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

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)

    # Try local server first (works on machines with browser)
    try:
        print("\nTrying local browser authentication...")
        # prompt="consent" is required here. access_type="offline" alone is not
        # enough: if this Google account has already authorized the app, Google
        # silently skips the consent screen and returns a token response with NO
        # refresh_token. The flow still "succeeds", so we would pickle a
        # useless credential and push it to GitHub, where unattended uploads
        # would keep failing with invalid_grant.
        #
        # open_browser=False: this machine has no default browser registered
        # for Python's `webbrowser` module, so letting run_local_server launch
        # one raises, and the fallback below re-issues authorization_url() with
        # a FRESH `state`. The consent already completed against the original
        # state then comes back to a flow that rejects it with
        # MismatchingStateError. Printing the URL and listening on :8080 keeps
        # a single state alive for the whole flow.
        credentials = flow.run_local_server(
            port=8080, access_type="offline", prompt="consent",
            open_browser=False,
        )
    except Exception:
        # Headless mode (Deepnote, SSH, etc.)
        print("\nNo browser detected — using manual URL mode.")
        print("-" * 50)

        auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

        print("\n1. OPEN this URL in your laptop browser:")
        print(f"\n   {auth_url}\n")
        print("2. Sign in with mohammedimthiyaz832@gmail.com")
        print("3. Click 'Allow'")
        print("4. Copy the AUTHORIZATION CODE from the browser")
        print("5. Paste it below and press Enter")
        print("-" * 50)

        auth_code = input("\nAuth code: ").strip()
        if not auth_code:
            print("ERROR: No code provided.")
            return False

        flow.fetch_token(code=auth_code)
        credentials = flow.credentials

    # Fail loudly before overwriting the token file. A pickle without a
    # refresh_token looks identical to a good one until CI tries to refresh.
    if not credentials.refresh_token:
        print("\n" + "=" * 50)
        print("ERROR: Google returned NO refresh_token.")
        print("This pickle would be useless to GitHub Actions.")
        print("")
        print("Fix: revoke this app's access, then re-run:")
        print("  https://myaccount.google.com/permissions")
        print("  (remove the app, confirm, run this script again)")
        print("=" * 50)
        return False

    # Save token
    with open(TOKEN_FILE, 'wb') as token:
        pickle.dump(credentials, token)

    print("\n" + "=" * 50)
    print("AUTHENTICATION SUCCESSFUL!")
    print(f"refresh_token: present ({len(credentials.refresh_token)} chars)")
    print(f"Token saved to: {TOKEN_FILE}")
    print("YouTube uploads will now work automatically.")
    print("=" * 50)

    return True

if __name__ == "__main__":
    authenticate()
