"""Service-account loading without printing secrets or credential paths."""
import json
import os
from pathlib import Path
import stat
from typing import Mapping
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

SCOPE = 'https://www.googleapis.com/auth/spreadsheets'


class CredentialError(RuntimeError):
    """Sanitized credential or token error."""


def credential_status(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    return 'Configured (not authenticated)' if env.get('GOOGLE_SERVICE_ACCOUNT_JSON') or env.get('GOOGLE_APPLICATION_CREDENTIALS') else 'Not configured'


def load_credentials(env: Mapping[str, str] | None = None) -> Credentials:
    env = os.environ if env is None else env
    inline, filename = env.get('GOOGLE_SERVICE_ACCOUNT_JSON'), env.get('GOOGLE_APPLICATION_CREDENTIALS')
    if bool(inline) == bool(filename):
        raise CredentialError('Configure exactly one service-account credential source.')
    try:
        if inline:
            if len(inline.encode()) > 65536:
                raise CredentialError('Credentials exceed the size limit.')
            raw = inline
        else:
            path = Path(filename)
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                raise CredentialError('Credentials must be a small regular file.')
            if os.name == 'posix' and (info.st_mode & 0o077 or info.st_uid != os.getuid()):
                raise CredentialError('Credential file must be owned by this user and protected with chmod 600.')
            raw = path.read_text()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get('type') != 'service_account':
            raise CredentialError('A service-account JSON credential is required.')
        if payload.get('token_uri') != 'https://oauth2.googleapis.com/token':
            raise CredentialError('Unexpected credential token endpoint.')
        return Credentials.from_service_account_info(payload, scopes=[SCOPE])
    except CredentialError:
        raise
    except (OSError, ValueError, TypeError, GoogleAuthError) as exc:
        raise CredentialError('Could not load service-account credentials. Check the protected configuration.') from exc


class AccessToken:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    def __call__(self) -> str:
        if not self.credentials.valid:
            session_request = Request()
            try:
                # google-auth otherwise uses a much longer default timeout.
                self.credentials.refresh(lambda **kwargs: session_request(**{**kwargs, 'timeout': 10}))
            except (GoogleAuthError, OSError, ValueError) as exc:
                raise CredentialError('Google authentication failed. Check the key, API access, and system clock.') from exc
        if not self.credentials.token:
            raise CredentialError('Google authentication did not return an access token.')
        return self.credentials.token
