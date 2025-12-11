"""
Auth Service.

Business logic for authentication operations.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from core.models import TokenBlacklist, User


class AuthService:
    """Authentication service handling OAuth and JWT operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_user_by_github_id(self, github_id: str) -> Optional[User]:
        """Get user by GitHub ID."""
        return self.session.query(User).filter(
            User.github_id == github_id
        ).first()
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID."""
        return self.session.query(User).filter(
            User.id == user_id
        ).first()
    
    def create_or_update_user(
        self,
        github_id: str,
        github_username: str,
        email: Optional[str] = None,
        avatar_url: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> User:
        """Create a new user or update existing one after OAuth."""
        user = self.get_user_by_github_id(github_id)
        
        if user:
            user.github_username = github_username
            if email:
                user.email = email
            if avatar_url:
                user.avatar_url = avatar_url
            if access_token:
                user.github_access_token = access_token
            user.updated_at = datetime.utcnow()
        else:
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
    
    def blacklist_token(self, token_jti: str, expires_at: datetime) -> None:
        """Add a token to the blacklist."""
        blacklist_entry = TokenBlacklist(
            token_jti=token_jti,
            expires_at=expires_at,
        )
        self.session.add(blacklist_entry)
        self.session.flush()
    
    def is_token_blacklisted(self, token_jti: str) -> bool:
        """Check if a token is blacklisted."""
        exists = self.session.query(TokenBlacklist).filter(
            TokenBlacklist.token_jti == token_jti,
            TokenBlacklist.expires_at > datetime.utcnow(),
        ).first()
        return exists is not None
    
    def cleanup_expired_blacklist(self) -> int:
        """Remove expired entries from the blacklist."""
        result = self.session.query(TokenBlacklist).filter(
            TokenBlacklist.expires_at <= datetime.utcnow()
        ).delete()
        self.session.flush()
        return result
