"""
One-time Jobber OAuth 2.0 setup script.
Manual callback flow — no local server needed.

Usage:
    python tools/auth_jobber.py
"""

import os
import sys
import base64
import urllib.parse
import webbrowser
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["JOBBER_CLIENT_ID"]
CLIENT_SECRET = os.environ["JOBBER_CLIENT_SECRET"]
REDIRECT_URI = "https://aboveexteriorcleaning.com/jobber-callback"

AUTH_URL = "https://api.getjobber.com/api/oauth/authorize"
TOKEN_URL = "https://api.getjobber.com/api/oauth/token"


def main():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("Opening Jobber authorization in your browser...")
    webbrowser.open(url)

    print("\nAfter you approve access, your browser will redirect to your website")
    print("and the page may show a 404 or not found — that's fine.")
    print("\nCopy the FULL URL from your browser's address bar and paste it here:")
    callback_url = input("> ").strip()

    parsed = urllib.parse.urlparse(callback_url)
    params = urllib.parse.parse_qs(parsed.query)

    auth_code = params.get("code", [None])[0]

    if not auth_code:
        print("No authorization code found in the URL. Make sure you copied the full URL.")
        sys.exit(1)

    print(f"\nCode received. Exchanging for tokens...")

    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        },
    )

    if not response.ok:
        print(f"Token exchange failed: {response.text}")
        sys.exit(1)

    tokens = response.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    print("\n" + "=" * 60)
    print("SUCCESS — Add these to your .env file:")
    print("=" * 60)
    print(f"JOBBER_ACCESS_TOKEN={access_token}")
    print(f"JOBBER_REFRESH_TOKEN={refresh_token}")
    print("=" * 60)
    print("\nDone! These tokens are now active.")


if __name__ == "__main__":
    main()
