"""
Cached Scoring Service.

Provides issue scoring with:
- Lazy ML model loading (3-tier cache: memory -> Redis -> disk)
- Cached score computation
- Batch scoring operations
"""

import hashlib
import logging
import os
import pickle
from typing import Any

import numpy as np

from core.cache import CacheKeys, cache
from core.constants import (
    CODE_FOCUSED_TYPES,
    SKILL_MATCH_WEIGHT,
)
from core.repositories import IssueRepository

logger = logging.getLogger(__name__)

# Model paths (from ml_trainer.py)
MODEL_PATH_V2 = os.getenv("ML_MODEL_PATH_V2", "models/xgboost_model_v2.pkl")
SCALER_PATH_V2 = os.getenv("ML_SCALER_PATH_V2", "models/scaler_v2.pkl")
FEATURE_SELECTOR_PATH_V2 = os.getenv("ML_FEATURE_SELECTOR_V2", "models/feature_selector_v2.pkl")
MODEL_PATH = os.getenv("ML_MODEL_PATH", "models/gradient_boosting_model.pkl")
SCALER_PATH = os.getenv("ML_SCALER_PATH", "models/scaler.pkl")


class ScoringService:
    """
    Scoring service with lazy ML model loading and caching.

    Features:
    - 3-tier ML model cache: memory -> Redis -> disk
    - Cached score computation with profile-based invalidation
    - Batch scoring for multiple issues

    Usage:
        from core.services import ScoringService
        from core.repositories import IssueRepository

        with db.session() as session:
            issue_repo = IssueRepository(session)
            scoring = ScoringService(issue_repo)

            # Get cached top matches
            top = scoring.get_top_matches(user_id, limit=10)

            # Score a single issue
            score = scoring.score_issue(issue, profile)
    """

    def __init__(self, issue_repo: IssueRepository | None = None):
        self.issue_repo = issue_repo

        # In-memory model cache
        self._model_v2: Any | None = None
        self._scaler_v2: Any | None = None
        self._feature_selector_v2: Any | None = None
        self._model_legacy: Any | None = None
        self._scaler_legacy: Any | None = None
        self._model_version: str | None = None

    # =========================================================================
    # Lazy ML Model Loading (3-tier cache)
    # =========================================================================

    def _load_model_component(
        self,
        cache_key: str,
        file_path: str,
        memory_attr: str,
    ) -> Any | None:
        """
        Load a model artifact using a 3-tier cache (memory -> Redis -> disk).

        Args:
            cache_key: Redis cache key for the artifact.
            file_path: Filesystem path to the pickled artifact.
            memory_attr: Attribute name used for the in-memory cache slot.

        Returns:
            The loaded artifact or None when unavailable.
        """
        # Tier 1: In-memory
        cached_value = getattr(self, memory_attr, None)
        if cached_value is not None:
            return cached_value

        # Tier 2: Redis
        cached_value = cache.get_model(cache_key)
        if cached_value is not None:
            logger.debug(f"Model loaded from Redis: {cache_key}")
            setattr(self, memory_attr, cached_value)
            return cached_value

        # Tier 3: Disk
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "rb") as f:
                value = pickle.load(f)

            # Cache in Redis (24 hour TTL)
            cache.set_model(cache_key, value, CacheKeys.TTL_DAY)
            setattr(self, memory_attr, value)
            logger.info(f"Model loaded from disk and cached: {file_path}")
            return value

        except Exception as e:
            logger.error(f"Error loading model from {file_path}: {e}")
            return None

    @property
    def model_v2(self) -> Any | None:
        """Lazy-load and cache the v2 XGBoost model artifact."""
        return self._load_model_component(
            cache_key=CacheKeys.ML_MODEL,
            file_path=MODEL_PATH_V2,
            memory_attr="_model_v2",
        )

    @property
    def scaler_v2(self) -> Any | None:
        """Lazy-load and cache the v2 feature scaler."""
        return self._load_model_component(
            cache_key=CacheKeys.ML_SCALER,
            file_path=SCALER_PATH_V2,
            memory_attr="_scaler_v2",
        )

    @property
    def feature_selector_v2(self) -> Any | None:
        """Lazy-load and cache the v2 feature selector."""
        return self._load_model_component(
            cache_key="ml:model:feature_selector",
            file_path=FEATURE_SELECTOR_PATH_V2,
            memory_attr="_feature_selector_v2",
        )

    @property
    def model_legacy(self) -> Any | None:
        """Lazy-load and cache the legacy model."""
        return self._load_model_component(
            cache_key="ml:model:legacy",
            file_path=MODEL_PATH,
            memory_attr="_model_legacy",
        )

    @property
    def scaler_legacy(self) -> Any | None:
        """Lazy-load and cache the legacy scaler."""
        return self._load_model_component(
            cache_key="ml:model:legacy_scaler",
            file_path=SCALER_PATH,
            memory_attr="_scaler_legacy",
        )

    def _get_model_version(self) -> str:
        """
        Determine the active model version based on available artifacts.

        Returns:
            Model version identifier: 'v2', 'legacy', or 'none'.
        """
        if self._model_version is not None:
            return self._model_version

        if self.model_v2 is not None and self.scaler_v2 is not None:
            self._model_version = "v2"
        elif self.model_legacy is not None and self.scaler_legacy is not None:
            self._model_version = "legacy"
        else:
            self._model_version = "none"

        return self._model_version

    def invalidate_model_cache(self) -> None:
        """Clear cached model artifacts from memory and Redis."""
        # Clear memory cache
        self._model_v2 = None
        self._scaler_v2 = None
        self._feature_selector_v2 = None
        self._model_legacy = None
        self._scaler_legacy = None
        self._model_version = None

        # Clear Redis cache
        cache.delete_pattern(CacheKeys.ml_pattern())
        logger.info("ML model cache invalidated")

    # =========================================================================
    # Scoring Methods
    # =========================================================================

    def predict_issue_quality(
        self,
        issue: dict,
        profile_data: dict | None = None,
    ) -> tuple[float, float]:
        """
        Predict issue quality using the available ML model with caching.

        Args:
            issue: Issue dictionary to score.
            profile_data: Optional profile context for feature extraction.

        Returns:
            Tuple of (probability_good, probability_bad).
        """
        # Import here to avoid circular imports
        from core.scoring.ml_trainer import extract_features

        model_version = self._get_model_version()

        if model_version == "v2":
            try:
                if (
                    self.feature_selector_v2 is None
                    or self.scaler_v2 is None
                    or self.model_v2 is None
                ):
                    raise ValueError("V2 model components not initialized")
                features = extract_features(issue, profile_data, use_advanced=True)
                X = np.array([features])
                X_selected = self.feature_selector_v2.transform(X)
                X_scaled = self.scaler_v2.transform(X_selected)
                proba = self.model_v2.predict_proba(X_scaled)[0]
                return proba[1], proba[0]
            except Exception as e:
                logger.warning(f"V2 model prediction failed: {e}")
                # Fall through to legacy
                self._model_version = None

        if model_version == "legacy" or self.model_legacy is not None:
            try:
                if self.scaler_legacy is None or self.model_legacy is None:
                    raise ValueError("Legacy model components not initialized")
                from core.scoring.ml_trainer import extract_features

                features = extract_features(issue, profile_data, use_advanced=False)
                X = np.array([features])
                X_scaled = self.scaler_legacy.transform(X)
                proba = self.model_legacy.predict_proba(X_scaled)[0]
                return proba[1], proba[0]
            except Exception as e:
                logger.warning(f"Legacy model prediction failed: {e}")

        # No model available
        return 0.5, 0.5

    def score_issue(
        self,
        issue: dict,
        profile: dict,
    ) -> dict:
        """
        Calculate a match score for an issue against a profile.

        Combines rule-based scoring with ML predictions to derive a bounded score.

        Args:
            issue: Issue dictionary including repo and metadata fields.
            profile: User profile dictionary containing skills and preferences.

        Returns:
            Dictionary containing total score, rule-based score, ML probabilities, and breakdown.
        """
        from core.scoring.issue_scorer import get_match_breakdown

        breakdown = get_match_breakdown(profile, issue)

        # Calculate weighted score (rule-based)
        skill_score = (breakdown["skills"]["match_percentage"] / 100.0) * SKILL_MATCH_WEIGHT
        experience_score = breakdown["experience"]["score"]
        repo_quality_score = breakdown["repo_quality"]["score"]
        freshness_score = breakdown["freshness"]["score"]
        time_match_score = breakdown["time_match"]["score"]
        interest_match_score = breakdown["interest_match"]["score"]

        rule_based_score = (
            skill_score
            + experience_score
            + repo_quality_score
            + freshness_score
            + time_match_score
            + interest_match_score
        )

        # Apply code-focused issue type bonus
        issue_type = issue.get("issue_type", "").lower() if issue.get("issue_type") else ""
        if issue_type in CODE_FOCUSED_TYPES:
            rule_based_score = rule_based_score * 1.1

        # Get ML prediction (using cached model)
        ml_good_prob, ml_bad_prob = self.predict_issue_quality(issue, profile)

        # Calculate ML adjustment
        ml_adjustment = 0.0
        if ml_good_prob > 0.7:
            ml_adjustment = (ml_good_prob - 0.7) * 50.0
        elif ml_bad_prob > 0.7:
            ml_adjustment = -(ml_bad_prob - 0.7) * 50.0

        # Combine scores (45% ML, 55% rule-based)
        ml_weight = 0.45
        adjusted_score = rule_based_score + (ml_adjustment * ml_weight)
        adjusted_score = max(0.0, min(100.0, adjusted_score))

        return {
            "total_score": adjusted_score,
            "rule_based_score": rule_based_score,
            "ml_good_prob": ml_good_prob,
            "ml_bad_prob": ml_bad_prob,
            "breakdown": breakdown,
        }

    def _profile_hash(self, profile: dict) -> str:
        """
        Generate a compact hash for a profile to key cached results.

        Args:
            profile: Profile data used for scoring.

        Returns:
            Short hash string suitable for cache keys.
        """
        # Use skills and experience level for hash (most impactful on scoring)
        key_parts = [
            ",".join(sorted(profile.get("skills", []))),
            profile.get("experience_level", ""),
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()[:8]

    def get_top_matches(
        self,
        user_id: int,
        profile: dict,
        limit: int = 10,
    ) -> list[dict]:
        """
        Retrieve top matching issues for a user with caching.

        Args:
            user_id: Target user identifier.
            profile: Profile data used for scoring.
            limit: Maximum number of issues to return.

        Returns:
            List of issue dictionaries ordered by score.
        """
        cache_key = f"{CacheKeys.user_top_matches(user_id, limit)}:{self._profile_hash(profile)}"

        # Try cache first
        cached_result = cache.get_json(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for top matches: {cache_key}")
            # Ensure cached result is a list
            if isinstance(cached_result, list):
                return cached_result
            # If it's a dict, wrap it in a list (shouldn't happen but handle gracefully)
            return [cached_result] if isinstance(cached_result, dict) else []

        # Compute top matches
        if self.issue_repo is None:
            raise ValueError("IssueRepository required for get_top_matches")

        # Get issues with precomputed scores if available
        issues = self.issue_repo.get_top_scored(user_id, limit * 2)  # Get more to filter

        if not issues:
            return []

        # If no cached scores, compute them
        results = []
        for issue in issues:
            issue_dict = issue.to_dict()
            if issue.cached_score is not None:
                issue_dict["score"] = issue.cached_score
            else:
                score_result = self.score_issue(issue_dict, profile)
                issue_dict["score"] = score_result["total_score"]
            results.append(issue_dict)

        # Sort by score and limit
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        results = results[:limit]

        # Cache result (5 min TTL)
        cache.set_json(cache_key, results, CacheKeys.TTL_SHORT)

        return results

    def batch_score_issues(
        self,
        user_id: int,
        profile: dict,
        batch_size: int = 100,
    ) -> int:
        """
        Batch score issues for a user and persist cached scores.

        Args:
            user_id: Target user identifier.
            profile: Profile data used for scoring.
            batch_size: Number of issues to process per iteration.

        Returns:
            Count of issues scored.
        """
        if self.issue_repo is None:
            raise ValueError("IssueRepository required for batch_score_issues")

        total_scored = 0
        offset = 0

        while True:
            issues = self.issue_repo.get_batch(user_id, offset, batch_size)
            if not issues:
                break

            scores = {}
            for issue in issues:
                issue_dict = issue.to_dict()
                score_result = self.score_issue(issue_dict, profile)
                scores[issue.id] = score_result["total_score"]

            # Bulk update scores
            self.issue_repo.update_cached_scores(scores)
            total_scored += len(scores)
            offset += batch_size

            logger.info(f"Scored {total_scored} issues for user {user_id}")

        # Invalidate top matches cache
        cache.delete_pattern(CacheKeys.user_pattern(user_id))

        return total_scored

    def invalidate_user_cache(self, user_id: int) -> int:
        """
        Remove all cached scoring data for a user.

        Args:
            user_id: Target user identifier.

        Returns:
            Number of deleted cache entries.
        """
        return cache.delete_pattern(CacheKeys.user_pattern(user_id))
