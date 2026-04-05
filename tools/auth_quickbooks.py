"""
One-time QuickBooks OAuth 2.0 setup script.
Uses a manual callback flow — no local server needed.

Usage:
    python tools/auth_quickbooks.py
"""

import os
import sys
import base64
import urllib.parse
import webbrowser
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["QB_CLIENT_ID"]
CLIENT_SECRET = os.environ["QB_CLIENT_SECRET"]
REDIRECT_URI = "https://aboveexteriorcleaning.com/qb-callback"

SCOPES = "com.intuit.quickbooks.accounting"
AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"


def main():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": "above-ai-auth",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("Opening QuickBooks authorization in your browser...")
    webbrowser.open(url)

    print("\nAfter you approve access, your browser will redirect to your website")
    print("and the page may show a 404 or not found — that's fine.")
    print("\nCopy the FULL URL from your browser's address bar and paste it here:")
    callback_url = input("> ").strip()

    parsed = urllib.parse.urlparse(callback_url)
    params = urllib.parse.parse_qs(parsed.query)

    auth_code = params.get("code", [None])[0]
    realm_id = params.get("realmId", [None])[0]

    if not auth_code:
        print("❌ No authorization code found in the URL. Make sure you copied the full URL.")
        sys.exit(1)

    print(f"\n✅ Code received. Company ID: {realm_id}")
    print("Exchanging for tokens...")

    credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    response = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        },
    )

    if not response.ok:
        print(f"❌ Token exchange failed: {response.text}")
        sys.exit(1)

    tokens = response.json()
    refresh_token = tokens.get("refresh_token")

    print("\n" + "=" * 60)
    print("✅ SUCCESS — Add these to your .env file:")
    print("=" * 60)
    print(f"QB_REFRESH_TOKEN={refresh_token}")
    if realm_id:
        print(f"QB_COMPANY_ID={realm_id}")
    print("=" * 60)
    print("\nDone! Refresh token is valid for 100 days and auto-renews on each sync.")


if __name__ == "__main__":
    main()
