"""
Utility functions for GitHub OAuth flow.
"""

from typing import Dict, Optional

import httpx

from ..config import get_settings

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"


def get_oauth_authorize_url(state: str) -> str:
    """Build GitHub OAuth authorize URL with client settings and state."""
    settings = get_settings()
    # Convert AnyHttpUrl to string to avoid serialization issues
    redirect_uri = str(settings.github_redirect_uri) if settings.github_redirect_uri else ""
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": redirect_uri,
        "scope": settings.github_scope,
        "state": state,
    }
    query = "&".join(f"{key}={httpx.QueryParams({key: value})[key]}" for key, value in params.items() if value)
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


def exchange_code_for_token(code: str) -> str:
    """
    Exchange GitHub OAuth code for an access token.

    Raises:
        ValueError when token is missing in the response.
    """
    settings = get_settings()
    # Convert AnyHttpUrl to string to avoid serialization issues
    redirect_uri = str(settings.github_redirect_uri) if settings.github_redirect_uri else None
    payload = {
        "client_id": settings.github_client_id,
        "client_secret": settings.github_client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json"}
    response = httpx.post(GITHUB_ACCESS_TOKEN_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    access_token = response.json().get("access_token")
    if not access_token:
        raise ValueError("GitHub OAuth token exchange failed")
    return access_token


def get_github_user(access_token: str) -> Dict[str, Optional[str]]:
    """Fetch GitHub user profile and primary email using the OAuth token."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(timeout=30) as client:
        user_resp = client.get(f"{GITHUB_API_URL}/user", headers=headers)
        user_resp.raise_for_status()
        user_data = user_resp.json()

        emails_resp = client.get(f"{GITHUB_API_URL}/user/emails", headers=headers)
        email = None
        if emails_resp.status_code == 200:
            for entry in emails_resp.json():
                if entry.get("primary"):
                    email = entry.get("email")
                    break

    return {
        "github_id": str(user_data.get("id")),
        "github_username": user_data.get("login"),
        "email": email or user_data.get("email"),
        "avatar_url": user_data.get("avatar_url"),
    }

