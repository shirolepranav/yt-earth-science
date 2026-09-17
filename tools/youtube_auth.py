"""One-off helper: get a YouTube refresh token.

You run this ONCE, on a machine with a web browser, and paste the token it
prints into your secrets. After that the pipeline can upload on its own,
forever, without you signing in again.

What a refresh token is: a long-lived pass that lets the pipeline ask Google for
a fresh access key whenever it needs one. It is as sensitive as a password -
never commit it, never paste it into a chat.

Before running this you need config/youtube_oauth.json, which you download from
Google Cloud Console:
  1. Create a project
  2. APIs & Services > Library > enable "YouTube Data API v3"
  3. OAuth consent screen > External > add yourself as a test user
  4. Credentials > Create credentials > OAuth client ID > Desktop app
  5. Download the JSON, save it as config/youtube_oauth.json

Then:  python tools/youtube_auth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRETS = ROOT / "config" / "youtube_oauth.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    if not CLIENT_SECRETS.exists():
        sys.exit(
            f"Missing {CLIENT_SECRETS}\n"
            "Download it from Google Cloud Console (see the notes at the top of this file)."
        )

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)

    # Opens a browser, then catches the redirect on a temporary local port.
    # access_type=offline is what makes Google issue a refresh token at all;
    # prompt=consent forces a new one even if you've authorised before.
    credentials = flow.run_local_server(
        port=0, access_type="offline", prompt="consent"
    )

    print("\n" + "=" * 70)
    print("Copy these three values into your secrets.")
    print("On GitHub: Settings > Secrets and variables > Actions > New secret")
    print("=" * 70)
    print(f"\nYOUTUBE_CLIENT_ID\n{credentials.client_id}")
    print(f"\nYOUTUBE_CLIENT_SECRET\n{credentials.client_secret}")
    print(f"\nYOUTUBE_REFRESH_TOKEN\n{credentials.refresh_token}")
    print("\n" + "=" * 70)
    print("Do not commit these. Do not paste them into a chat window.")


if __name__ == "__main__":
    main()
