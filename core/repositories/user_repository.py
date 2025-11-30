"""
User repository for authentication and user management.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from core.models import TokenBlacklist, User

from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""
    
    model = User
    
    def __init__(self, session: Session):
        super().__init__(session)
    
    def get_by_github_id(self, github_id: str) -> Optional[User]:
        """Get user by GitHub ID."""
        return (
            self.session.query(User)
            .filter(User.github_id == github_id)
            .first()
        )
    
    def get_by_github_username(self, username: str) -> Optional[User]:
        """Get user by GitHub username."""
        return (
            self.session.query(User)
            .filter(User.github_username == username)
            .first()
        )
    
    def create_or_update_from_github(
        self,
        github_id: str,
        github_username: str,
        email: Optional[str] = None,
        avatar_url: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> User:
        """
        Create or update a user from GitHub OAuth data.
        
        Used during OAuth callback to ensure user exists.
        """
        user = self.get_by_github_id(github_id)
        
        if user:
            # Update existing user
            user.github_username = github_username
            if email:
                user.email = email
            if avatar_url:
                user.avatar_url = avatar_url
            if access_token:
                user.github_access_token = access_token
            user.updated_at = datetime.utcnow()
        else:
            # Create new user
            user = User(
                github_id=github_id,
                github_username=github_username,
                email=email,
                avatar_url=avatar_url,
                github_access_token=access_token,
            )
            self.session.add(user)
        
        self.session.flush()
        return user
    
    def update_access_token(self, user_id: int, access_token: str) -> bool:
        """Update user's GitHub access token."""
        user = self.get_by_id(user_id)
        if user:
            user.github_access_token = access_token
            user.updated_at = datetime.utcnow()
            self.session.flush()
            return True
        return False


class TokenBlacklistRepository(BaseRepository[TokenBlacklist]):
    """Repository for managing blacklisted JWT tokens."""
    
    model = TokenBlacklist
    
    def __init__(self, session: Session):
        super().__init__(session)
    
    def is_blacklisted(self, token_jti: str) -> bool:
        """Check if a token JTI is blacklisted."""
        return (
            self.session.query(TokenBlacklist)
            .filter(TokenBlacklist.token_jti == token_jti)
            .first()
        ) is not None
    
    def blacklist_token(self, token_jti: str, expires_at: datetime) -> TokenBlacklist:
        """Add a token to the blacklist."""
        token = TokenBlacklist(
            token_jti=token_jti,
            expires_at=expires_at,
        )
        self.session.add(token)
        self.session.flush()
        return token
    
    def cleanup_expired(self) -> int:
        """Remove expired tokens from blacklist."""
        result = (
            self.session.query(TokenBlacklist)
            .filter(TokenBlacklist.expires_at < datetime.utcnow())
            .delete()
        )
        self.session.flush()
        return result

