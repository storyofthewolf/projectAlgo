# projectAlgo/scripts/schwab_auth.py
# One-time OAuth2 login flow for Schwab. Run this the first time, or whenever
# the token file expires (every 7 days).
#
# Usage:
#   python -m scripts.schwab_auth
#
# The browser will open for Schwab login. After approving, paste the redirect
# URL back into the terminal. The token file is saved automatically.

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import schwab
except ImportError:
    raise SystemExit("schwab-py is not installed. Run: pip install schwab-py")


def main():
    app_key = os.environ.get('SCHWAB_APP_KEY')
    app_secret = os.environ.get('SCHWAB_APP_SECRET')
    token_path = os.environ.get('SCHWAB_TOKEN_PATH', str(Path.home() / '.schwab_token.json'))
    callback_url = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182')

    if not app_key or not app_secret:
        raise SystemExit(
            "SCHWAB_APP_KEY and SCHWAB_APP_SECRET must be set.\n"
            "See config/schwab_config.example.env for the template."
        )

    print(f"Starting Schwab OAuth login flow...")
    print(f"Token will be saved to: {token_path}")
    print(f"Callback URL: {callback_url}\n")

    schwab.auth.client_from_login_flow(
        app_key, app_secret, callback_url, token_path
    )
    print(f"\nAuthentication successful. Token saved to {token_path}")
    print("You can now run account and quote commands.")


if __name__ == '__main__':
    main()
