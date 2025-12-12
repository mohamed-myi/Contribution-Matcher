"""User repository for authentication and user management."""

from datetime import datetime, timezone

from core.logging import get_logger
from core.models import TokenBlacklist, User
from core.security.encryption import get_encryption_service

from .base import BaseRepository

logger = get_logger("repository.user")


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""

    model = User

    def get_by_github_id(self, github_id: str) -> User | None:
        """Get user by GitHub ID."""
        return self.session.query(User).filter(User.github_id == github_id).first()

    def get_by_github_username(self, username: str) -> User | None:
        """Get user by GitHub username."""
        return self.session.query(User).filter(User.github_username == username).first()

    def _encrypt_token(self, token: str) -> str:
        """
        Encrypt a GitHub access token for secure storage.

        Falls back to plaintext if encryption is unavailable,
        but logs a warning for security auditing.
        """
        encryption = get_encryption_service()
        encrypted, was_encrypted = encryption.encrypt_if_available(token)

        if not was_encrypted:
            logger.warning(
                "token_stored_unencrypted",
                message="GitHub token stored without encryption. Set TOKEN_ENCRYPTION_KEY for secure storage.",
            )

        return encrypted

    def get_decrypted_token(self, user: User) -> str | None:
        """
        Get the decrypted GitHub access token for a user.

        Args:
            user: User model instance

        Returns:
            Decrypted token or None if no token exists
        """
        if not user.github_access_token:
            return None

        encryption = get_encryption_service()
        return encryption.decrypt_if_encrypted(user.github_access_token)

    def create_or_update_from_github(
        self,
        github_id: str,
        github_username: str,
        email: str | None = None,
        avatar_url: str | None = None,
        access_token: str | None = None,
    ) -> User:
        """
        Create or update a user from GitHub OAuth data.

        The access_token is encrypted before storage if TOKEN_ENCRYPTION_KEY
        is configured. This protects tokens at rest in the database.
        """
        user = self.get_by_github_id(github_id)

        # Encrypt the token if provided
        encrypted_token = self._encrypt_token(access_token) if access_token else None

        if user:
            user.github_username = github_username
            if email:
                user.email = email
            if avatar_url:
                user.avatar_url = avatar_url
            if encrypted_token:
                user.github_access_token = encrypted_token
            user.updated_at = datetime.now(timezone.utc)
        else:
            user = User(
                github_id=github_id,
                github_username=github_username,
                email=email,
                avatar_url=avatar_url,
                github_access_token=encrypted_token,
            )
            self.session.add(user)

        self.session.flush()
        return user

    def update_access_token(self, user_id: int, access_token: str) -> bool:
        """
        Update user's GitHub access token.

        The token is encrypted before storage if TOKEN_ENCRYPTION_KEY is configured.
        """
        user = self.get_by_id(user_id)
        if user:
            user.github_access_token = self._encrypt_token(access_token)
            user.updated_at = datetime.now(timezone.utc)
            self.session.flush()
            return True
        return False


class TokenBlacklistRepository(BaseRepository[TokenBlacklist]):
    """Repository for managing blacklisted JWT tokens."""

    model = TokenBlacklist

    def is_blacklisted(self, token_jti: str) -> bool:
        """Check if a token JTI is blacklisted."""
        return self.exists_where(token_jti=token_jti)

    def blacklist_token(self, token_jti: str, expires_at: datetime) -> TokenBlacklist:
        """Add a token to the blacklist."""
        token = TokenBlacklist(token_jti=token_jti, expires_at=expires_at)
        self.session.add(token)
        self.session.flush()
        return token

    def cleanup_expired(self) -> int:
        """Remove expired tokens from blacklist."""
        result = (
            self.session.query(TokenBlacklist)
            .filter(TokenBlacklist.expires_at < datetime.now(timezone.utc))
            .delete()
        )
        self.session.flush()
        return result
