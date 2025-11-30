"""
Cache key management.

Centralized cache key definitions to:
- Prevent key collisions
- Enable pattern-based invalidation
- Document cache structure
"""

from typing import Optional


class CacheKeys:
    """
    Centralized cache key definitions.
    
    Naming convention: {domain}:{entity}:{id}:{subtype}
    
    Examples:
        - user:123:scores -> User's computed scores
        - user:123:top_matches:10 -> User's top 10 matches
        - ml:model:scorer -> ML scorer model
        - repo:owner/name:metadata -> Repository metadata
    """
    
    # Prefixes for different domains
    PREFIX_USER = "user"
    PREFIX_ML = "ml"
    PREFIX_REPO = "repo"
    PREFIX_ISSUE = "issue"
    PREFIX_GITHUB = "github"
    
    # TTLs (in seconds)
    TTL_SHORT = 60 * 5        # 5 minutes
    TTL_MEDIUM = 60 * 30      # 30 minutes
    TTL_LONG = 60 * 60 * 6    # 6 hours
    TTL_DAY = 60 * 60 * 24    # 24 hours
    
    # ML Model Keys
    ML_MODEL = "ml:model:scorer"
    ML_SCALER = "ml:model:scaler"
    ML_EMBEDDER = "ml:model:embedder"
    
    # GitHub API Keys
    GITHUB_RATE_LIMIT = "github:rate_limit"
    GITHUB_GRAPHQL_RATE_LIMIT = "github:graphql_rate_limit"
    
    @staticmethod
    def user_scores(user_id: int) -> str:
        """Cache key for user's issue scores."""
        return f"user:{user_id}:scores"
    
    @staticmethod
    def user_top_matches(user_id: int, limit: int = 10) -> str:
        """Cache key for user's top N matches."""
        return f"user:{user_id}:top_matches:{limit}"
    
    @staticmethod
    def user_profile(user_id: int) -> str:
        """Cache key for user's profile data."""
        return f"user:{user_id}:profile"
    
    @staticmethod
    def user_issues(user_id: int, page: int = 0) -> str:
        """Cache key for paginated user issues."""
        return f"user:{user_id}:issues:page:{page}"
    
    @staticmethod
    def repo_metadata(owner: str, name: str) -> str:
        """Cache key for repository metadata."""
        return f"repo:{owner}/{name}:metadata"
    
    @staticmethod
    def issue_embedding(issue_id: int) -> str:
        """Cache key for issue embedding."""
        return f"issue:{issue_id}:embedding"
    
    @staticmethod
    def issue_features(issue_id: int, profile_hash: Optional[str] = None) -> str:
        """Cache key for issue feature vector."""
        if profile_hash:
            return f"issue:{issue_id}:features:{profile_hash}"
        return f"issue:{issue_id}:features"
    
    # Pattern keys for bulk invalidation
    @staticmethod
    def user_pattern(user_id: int) -> str:
        """Pattern to match all cache keys for a user."""
        return f"user:{user_id}:*"
    
    @staticmethod
    def ml_pattern() -> str:
        """Pattern to match all ML model cache keys."""
        return "ml:model:*"

