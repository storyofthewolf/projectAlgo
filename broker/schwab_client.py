# projectAlgo/broker/schwab_client.py
# Manages Schwab OAuth2 authentication and produces a shared Client instance.
#
# Required environment variables (set in .env or shell):
#   SCHWAB_APP_KEY      - from Schwab developer portal
#   SCHWAB_APP_SECRET   - from Schwab developer portal
#   SCHWAB_TOKEN_PATH   - path to token file (default: ~/.schwab_token.json)
#   SCHWAB_CALLBACK_URL - OAuth callback URL (default: https://127.0.0.1:8182)
#
# Token files expire every 7 days and require re-authentication via schwab_auth.py.

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be set directly in shell

_client = None  # module-level singleton


def _get_credentials() -> tuple[str, str, str, str]:
    """Returns (app_key, app_secret, token_path, callback_url) from environment."""
    app_key = os.environ.get('SCHWAB_APP_KEY')
    app_secret = os.environ.get('SCHWAB_APP_SECRET')
    token_path = os.environ.get('SCHWAB_TOKEN_PATH', str(Path.home() / '.schwab_token.json'))
    callback_url = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182')

    missing = [name for name, val in [('SCHWAB_APP_KEY', app_key), ('SCHWAB_APP_SECRET', app_secret)] if not val]
    if missing:
        raise EnvironmentError(
            f"Missing Schwab credentials: {', '.join(missing)}\n"
            "Set these environment variables or create a .env file.\n"
            "See config/schwab_config.example.env for the template."
        )
    return app_key, app_secret, token_path, callback_url


def is_authenticated() -> bool:
    """Returns True if credentials are set and a token file exists."""
    try:
        app_key, app_secret, token_path, _ = _get_credentials()
        return bool(app_key and app_secret and Path(token_path).exists())
    except EnvironmentError:
        return False


def get_client():
    """
    Returns a schwab.Client, creating it on first call (singleton).
    Uses an existing token file if present; raises if not authenticated.
    Run scripts/schwab_auth.py to create the token file for the first time.
    """
    global _client
    if _client is not None:
        return _client

    try:
        import schwab
    except ImportError:
        raise ImportError(
            "schwab-py is not installed. Run: pip install schwab-py"
        )

    app_key, app_secret, token_path, _ = _get_credentials()

    if not Path(token_path).exists():
        raise FileNotFoundError(
            f"Schwab token file not found at: {token_path}\n"
            "Run 'python -m scripts.schwab_auth' to authenticate for the first time."
        )

    _client = schwab.auth.client_from_token_file(token_path, app_key, app_secret)
    return _client


def reset_client():
    """Clears the cached client (useful after token refresh or in tests)."""
    global _client
    _client = None
