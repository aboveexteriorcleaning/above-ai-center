"""
One-time Google OAuth setup to add Sheets scope to existing credentials.
Run this once to get a refresh token that covers both Business Profile and Sheets.

Usage:
    python tools/auth_google_sheets.py
"""

import os
import json
import webbrowser
import urllib.parse
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = "https://aboveexteriorcleaning.com/google-callback"

SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def main():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("Opening Google authorization in your browser...")
    print("Make sure you're logged in as the Google account that owns the sheet.\n")
    webbrowser.open(url)

    print("After you approve access, your browser will redirect to your website.")
    print("The page may show a 404 — that's fine.")
    print("Copy the FULL URL from your browser's address bar and paste it here:")
    callback_url = input("> ").strip()

    parsed = urllib.parse.urlparse(callback_url)
    params_qs = urllib.parse.parse_qs(parsed.query)
    code = params_qs.get("code", [None])[0]
    if not code:
        print("No code found in URL. Make sure you copied the full URL.")
        return

    resp = requests.post(TOKEN_URL, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })

    if not resp.ok:
        print(f"Token exchange failed: {resp.text}")
        return

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        print("No refresh token returned. Try running again — make sure to approve all permissions.")
        return

    print("\n" + "=" * 60)
    print("SUCCESS — Update your .env file:")
    print("=" * 60)
    print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
    print("=" * 60)
    print("\nThis token now covers both Google Business Profile and Sheets.")


if __name__ == "__main__":
    main()
