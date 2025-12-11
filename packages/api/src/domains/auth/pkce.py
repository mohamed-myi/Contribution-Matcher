"""
PKCE (Proof Key for Code Exchange) Implementation.

Implements OAuth 2.1 PKCE flow to prevent authorization code interception attacks.

PKCE Flow:
1. Client generates code_verifier (random string) and code_challenge (SHA256 hash)
2. Client includes code_challenge in authorization request
3. After receiving auth code, client sends code_verifier with token request
4. Server verifies code_verifier matches original code_challenge

This implementation:
- Uses S256 method (SHA256 hash) as required by OAuth 2.1
- Generates cryptographically secure random verifiers
- Validates state parameter for CSRF protection
- Stores pending challenges in Redis with TTL
"""

import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

import redis


class PKCEManager:
    """
    Manages PKCE flow for OAuth 2.1 authentication.
    
    Usage:
        pkce = PKCEManager(redis_client)
        
        # Generate challenge for authorization
        verifier, challenge, state = pkce.generate_challenge()
        
        # Redirect user with challenge
        # ...
        
        # On callback, verify the code
        is_valid = pkce.verify_challenge(state, code_verifier)
    """
    
    VERIFIER_LENGTH = 64  # 64 bytes = 512 bits
    STATE_LENGTH = 32  # 32 bytes = 256 bits
    CHALLENGE_TTL = 600  # 10 minutes
    REDIS_KEY_PREFIX = "oauth:pkce:"
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self._pending_challenges: dict = {}  # Fallback if no Redis
    
    def generate_verifier(self) -> str:
        """
        Generate a cryptographically secure code verifier.
        
        The verifier is a URL-safe base64 encoded random string.
        Length: 43-128 characters (we use 86 characters from 64 bytes).
        
        Returns:
            Code verifier string
        """
        random_bytes = secrets.token_bytes(self.VERIFIER_LENGTH)
        return base64.urlsafe_b64encode(random_bytes).decode("ascii").rstrip("=")
    
    def generate_challenge(self, verifier: str) -> str:
        """
        Generate code challenge from verifier using S256 method.
        
        S256 method: BASE64URL(SHA256(code_verifier))
        
        Args:
            verifier: The code verifier string
        
        Returns:
            Code challenge string
        """
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    
    def generate_state(self) -> str:
        """
        Generate a random state parameter for CSRF protection.
        
        Returns:
            State string
        """
        return secrets.token_urlsafe(self.STATE_LENGTH)
    
    def create_authorization_params(self) -> Tuple[str, str, str]:
        """
        Create all parameters needed for authorization request.
        
        Returns:
            Tuple of (code_verifier, code_challenge, state)
            
            - code_verifier: Keep secret, use in token exchange
            - code_challenge: Include in authorization URL
            - state: Include in authorization URL, verify on callback
        """
        verifier = self.generate_verifier()
        challenge = self.generate_challenge(verifier)
        state = self.generate_state()
        
        # Store verifier with state for later verification
        self._store_pending_challenge(state, verifier)
        
        return verifier, challenge, state
    
    def _store_pending_challenge(self, state: str, verifier: str) -> None:
        """Store the code verifier associated with state."""
        key = f"{self.REDIS_KEY_PREFIX}{state}"
        
        if self.redis_client:
            self.redis_client.setex(key, self.CHALLENGE_TTL, verifier)
        else:
            # Fallback to in-memory storage
            expires_at = datetime.utcnow() + timedelta(seconds=self.CHALLENGE_TTL)
            self._pending_challenges[state] = {
                "verifier": verifier,
                "expires_at": expires_at,
            }
    
    def get_verifier(self, state: str) -> Optional[str]:
        """
        Retrieve the code verifier for a given state.
        
        Args:
            state: The state parameter from callback
        
        Returns:
            Code verifier if found and not expired, None otherwise
        """
        key = f"{self.REDIS_KEY_PREFIX}{state}"
        
        if self.redis_client:
            verifier = self.redis_client.get(key)
            if verifier:
                # Delete after retrieval (one-time use)
                self.redis_client.delete(key)
                return verifier
            return None
        else:
            # Fallback to in-memory
            data = self._pending_challenges.pop(state, None)
            if data:
                if datetime.utcnow() < data["expires_at"]:
                    return data["verifier"]
            return None
    
    def verify_challenge(self, state: str, code_verifier: str) -> bool:
        """
        Verify that the code verifier matches the stored challenge.
        
        Args:
            state: The state parameter from callback
            code_verifier: The code verifier from client
        
        Returns:
            True if verification succeeds
        """
        stored_verifier = self.get_verifier(state)
        
        if not stored_verifier:
            return False
        
        # Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(stored_verifier, code_verifier)
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired pending challenges (in-memory fallback only).
        
        Returns:
            Number of expired entries removed
        """
        if self.redis_client:
            # Redis handles TTL automatically
            return 0
        
        now = datetime.utcnow()
        expired_states = [
            state for state, data in self._pending_challenges.items()
            if data["expires_at"] <= now
        ]
        
        for state in expired_states:
            del self._pending_challenges[state]
        
        return len(expired_states)


def build_github_authorization_url(
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
    scope: str = "read:user user:email",
) -> str:
    """
    Build the GitHub OAuth authorization URL with PKCE.
    
    Args:
        client_id: GitHub OAuth app client ID
        redirect_uri: Callback URL
        code_challenge: PKCE code challenge
        state: State parameter for CSRF protection
        scope: OAuth scopes to request
    
    Returns:
        Full authorization URL
    """
    from urllib.parse import urlencode
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "response_type": "code",
    }
    
    base_url = "https://github.com/login/oauth/authorize"
    return f"{base_url}?{urlencode(params)}"


async def exchange_code_for_token(
    code: str,
    code_verifier: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """
    Exchange authorization code for access token using PKCE.
    
    Args:
        code: Authorization code from callback
        code_verifier: PKCE code verifier
        client_id: GitHub OAuth app client ID
        client_secret: GitHub OAuth app client secret
        redirect_uri: Callback URL (must match authorization request)
    
    Returns:
        Token response dictionary with access_token and other fields
    """
    import httpx
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            headers={
                "Accept": "application/json",
            },
        )
        
        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")
        
        return response.json()
