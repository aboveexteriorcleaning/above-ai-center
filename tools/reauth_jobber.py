"""
Jobber OAuth reauthorization helper.

Run this once when the refresh token is expired or invalid.
It will:
  1. Open the Jobber authorization page in your browser
  2. Catch the redirect on localhost:8080
  3. Exchange the code for new tokens
  4. Print the new JOBBER_ACCESS_TOKEN and JOBBER_REFRESH_TOKEN to paste into .env

Before running:
  - Make sure http://localhost:8080 is registered as a redirect URI in your
    Jobber Developer Center app settings (developer.getjobber.com)

Usage:
    .venv/bin/python tools/reauth_jobber.py
"""

import os
import webbrowser
import urllib.parse
import http.server
import threading
import requests
from dotenv import load_dotenv

load_dotenv()

REDIRECT_URI = "http://localhost:8080"
CLIENT_ID = os.environ["JOBBER_CLIENT_ID"]
CLIENT_SECRET = os.environ["JOBBER_CLIENT_SECRET"]

AUTH_URL = (
    "https://api.getjobber.com/api/oauth/authorize"
    f"?response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
)

TOKEN_URL = "https://api.getjobber.com/api/oauth/token"

# Shared storage for the auth code captured by the local server
_code_holder = {"code": None}
_server_done = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]

        if code:
            _code_holder["code"] = code
            body = b"<h2>Authorization successful! You can close this tab.</h2>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)
        else:
            error = params.get("error", ["unknown"])[0]
            body = f"<h2>Authorization failed: {error}</h2>".encode()
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        _server_done.set()

    def log_message(self, format, *args):
        pass  # suppress request logging


def main():
    # Start local callback server
    server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print(f"\nOpening Jobber authorization in your browser...")
    print(f"If it doesn't open automatically, visit:\n  {AUTH_URL}\n")
    webbrowser.open(AUTH_URL)

    # Wait for the callback
    _server_done.wait(timeout=120)
    thread.join()

    code = _code_holder["code"]
    if not code:
        print("ERROR: No authorization code received. Did you authorize the app?")
        return

    print("Authorization code received. Exchanging for tokens...")

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
    )

    if not resp.ok:
        print(f"ERROR: Token exchange failed ({resp.status_code}):\n{resp.text}")
        return

    data = resp.json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    if not access_token or not refresh_token:
        print(f"ERROR: Unexpected response:\n{data}")
        return

    print("\n" + "=" * 60)
    print("SUCCESS — paste these into your .env file:")
    print("=" * 60)
    print(f"\nJOBBER_ACCESS_TOKEN={access_token}")
    print(f"JOBBER_REFRESH_TOKEN={refresh_token}")
    print("\n" + "=" * 60)
    print("After updating .env, run:")
    print("  .venv/bin/python tools/sync_jobber.py --mode full")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
