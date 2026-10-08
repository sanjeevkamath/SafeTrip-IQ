"""Backend-only client configuration for maintenance scripts.

Credential shape checks prevent configuration mistakes; Supabase verifies the
credential itself. Never import this module into the frontend.
"""

import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse


ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


def writer_credentials(environ):
    """Fail closed: a public key is never a fallback for a maintenance job."""
    url = environ.get("SUPABASE_URL", "").strip()
    secret = environ.get("SUPABASE_SECRET_KEY", "").strip()
    legacy = environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    parsed = urlparse(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ValueError("SUPABASE_URL must be an HTTPS project URL.")
    if secret and legacy:
        raise ValueError("Set only one backend writer credential variable.")
    if secret:
        if not secret.startswith("sb_secret_") or len(secret) <= len("sb_secret_"):
            raise ValueError("SUPABASE_SECRET_KEY must contain a backend secret key.")
        return url, secret
    if not legacy:
        raise ValueError(
            "Set SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY in the root "
            ".env. Public/ANON_KEY credentials cannot be used for writes."
        )
    try:
        parts = legacy.split(".")
        if len(parts) != 3:
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(
            parts[1] + "=" * (-len(parts[1]) % 4)
        ))
        if not isinstance(payload, dict) or payload.get("role") != "service_role":
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        raise ValueError(
            "SUPABASE_SERVICE_ROLE_KEY must contain a legacy service_role JWT."
        ) from None
    return url, legacy


def get_writer_client():
    # Lazy imports let credential checks run without installing the ML stack.
    from dotenv import load_dotenv
    from supabase import create_client

    # Explicit process variables win over the ignored root .env file.
    load_dotenv(ROOT_ENV, override=False)
    url, key = writer_credentials(os.environ)
    return create_client(url, key)
