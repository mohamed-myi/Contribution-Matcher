"""
Advanced Feature Extraction Module

This module extracts advanced features for ML training, including:
- Text embeddings (BERT) for issue descriptions and titles
- Interaction features between base features
- Polynomial feature expansion
- Temporal features (freshness, days since creation)
"""

import pickle
from datetime import datetime

import numpy as np
from sklearn.preprocessing import PolynomialFeatures

# Global embedding model (lazy loaded)
_embedding_model = None
_embedding_model_name = "all-MiniLM-L6-v2"


def _get_embedding_model():
    """
    Lazily load the sentence transformer model for embeddings.

    Returns:
        Loaded SentenceTransformer instance.
    """
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedding_model = SentenceTransformer(_embedding_model_name)
        except ImportError:
            raise ImportError(
                "sentence-transformers package is required for advanced features. "
                "Install with: pip install sentence-transformers"
            )
    return _embedding_model


def get_text_embeddings(issue: dict, session=None) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate BERT embeddings for an issue body and title with caching.

    Args:
        issue: Issue dictionary containing body, title, and optional id.
        session: Optional SQLAlchemy session for caching embeddings.

    Returns:
        Tuple of numpy arrays (description_embedding, title_embedding).
    """
    issue_id = issue.get("id")

    # Try to load from cache using ORM if session is provided
    if issue_id and session:
        try:
            from core.models import IssueEmbedding

            cached = (
                session.query(IssueEmbedding).filter(IssueEmbedding.issue_id == issue_id).first()
            )
            if cached and cached.description_embedding and cached.title_embedding:
                desc_emb = pickle.loads(cached.description_embedding)
                title_emb = pickle.loads(cached.title_embedding)
                return desc_emb, title_emb
        except Exception:
            pass

    # Generate embeddings
    model = _get_embedding_model()

    description = issue.get("body", "") or ""
    title = issue.get("title", "") or ""

    description_embedding = model.encode(description, convert_to_numpy=True)
    title_embedding = model.encode(title, convert_to_numpy=True)

    # Cache in database if session provided
    if issue_id and session:
        try:
            from core.models import IssueEmbedding

            existing = (
                session.query(IssueEmbedding).filter(IssueEmbedding.issue_id == issue_id).first()
            )

            desc_blob = pickle.dumps(description_embedding)
            title_blob = pickle.dumps(title_embedding)

            if existing:
                existing.description_embedding = desc_blob
                existing.title_embedding = title_blob
                existing.embedding_model = _embedding_model_name
            else:
                embedding = IssueEmbedding(
                    issue_id=issue_id,
                    description_embedding=desc_blob,
                    title_embedding=title_blob,
                    embedding_model=_embedding_model_name,
                )
                session.add(embedding)
            session.flush()
        except Exception:
            pass

    return description_embedding, title_embedding


def extract_interaction_features(base_features: list[float]) -> list[float]:
    """
    Compute interaction features between key base features.

    Args:
        base_features: List of 14 base features.

    Returns:
        List of 12 interaction feature values.
    """
    if len(base_features) < 11:
        return [0.0] * 12

    # Map base features (assuming order from extract_features)
    # Feature 1: num_technologies
    # Feature 2: skill_match_pct (if profile available)
    # Feature 3: experience_score
    # Feature 4: repo_quality_score
    # Feature 5: freshness_score
    # Feature 6: time_match_score
    # Feature 7: interest_match_score
    # Feature 8: total_rule_score
    # Feature 9: repo_stars
    # Feature 10: repo_forks
    # Feature 11: contributor_count

    # Extract with safe indexing
    num_tech = base_features[0] if len(base_features) > 0 else 0.0
    skill_match = base_features[1] if len(base_features) > 1 else 0.0
    exp_score = base_features[2] if len(base_features) > 2 else 0.0
    repo_quality = base_features[3] if len(base_features) > 3 else 0.0
    freshness = base_features[4] if len(base_features) > 4 else 0.0
    time_match = base_features[5] if len(base_features) > 5 else 0.0
    interest_match = base_features[6] if len(base_features) > 6 else 0.0
    total_score = base_features[7] if len(base_features) > 7 else 0.0
    stars = base_features[8] if len(base_features) > 8 else 0.0
    forks = base_features[9] if len(base_features) > 9 else 0.0
    contributors = base_features[10] if len(base_features) > 10 else 0.0

    interactions = [
        skill_match * exp_score,  # Skill × Experience
        skill_match * repo_quality,  # Skill × Repo Quality
        exp_score * repo_quality,  # Experience × Repo Quality
        freshness * repo_quality,  # Freshness × Repo Quality
        time_match * exp_score,  # Time × Experience
        interest_match * skill_match,  # Interest × Skill
        num_tech * skill_match,  # Tech Count × Skill Match
        stars * repo_quality,  # Stars × Repo Quality
        forks * contributors,  # Forks × Contributors
        freshness * time_match,  # Freshness × Time Match
        total_score * repo_quality,  # Total Score × Repo Quality
        skill_match * total_score,  # Skill × Total Score
    ]

    return interactions


def extract_polynomial_features(base_features: list[float]) -> list[float]:
    """
    Generate degree-2 polynomial features from selected numeric inputs.

    Args:
        base_features: List of base features.

    Returns:
        List of 27 polynomial features (6 original, 6 squared, 15 cross terms).
    """
    if len(base_features) < 8:
        return [0.0] * 27

    # Select 6 key features for polynomial expansion
    key_features = [
        base_features[1] if len(base_features) > 1 else 0.0,  # skill_match_pct
        base_features[2] if len(base_features) > 2 else 0.0,  # experience_score
        base_features[3] if len(base_features) > 3 else 0.0,  # repo_quality_score
        base_features[4] if len(base_features) > 4 else 0.0,  # freshness_score
        base_features[5] if len(base_features) > 5 else 0.0,  # time_match_score
        base_features[7] if len(base_features) > 7 else 0.0,  # total_rule_score
    ]

    # Use sklearn's PolynomialFeatures for degree 2
    poly = PolynomialFeatures(degree=2, include_bias=False)
    key_features_array = np.array([key_features])
    poly_features = poly.fit_transform(key_features_array)[0]

    # Return as list (should be 6 + 6 + 15 = 27 features)
    return poly_features.tolist()


def _parse_date_to_days(date_value, default_days: float = 365.0) -> float:
    """
    Convert a date value to days elapsed from now.

    Args:
        date_value: ISO string or datetime to parse.
        default_days: Fallback days when parsing fails.

    Returns:
        Days elapsed since date_value.
    """
    if not date_value:
        return default_days

    try:
        if isinstance(date_value, str):
            date_obj = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        else:
            date_obj = date_value
        days = (datetime.now() - date_obj.replace(tzinfo=None)).days
        return float(days)
    except (ValueError, AttributeError, TypeError):
        return default_days


def extract_temporal_features(issue: dict) -> list[float]:
    """
    Derive temporal features from issue creation and update timestamps.

    Args:
        issue: Issue dictionary containing created_at and updated_at.

    Returns:
        List of five temporal feature values.
    """
    days_since_created = _parse_date_to_days(issue.get("created_at"))
    days_since_updated = _parse_date_to_days(issue.get("updated_at"))

    # Freshness score (1.0 for today, decaying)
    freshness_score = max(0.0, 1.0 - (days_since_updated / 365.0))

    # Is recent (posted < 7 days)
    is_recent = 1.0 if days_since_created < 7 else 0.0

    # Is stale (posted > 30 days)
    is_stale = 1.0 if days_since_created > 30 else 0.0

    return [
        days_since_created,
        days_since_updated,
        freshness_score,
        is_recent,
        is_stale,
    ]


def extract_advanced_features(
    issue: dict,
    profile_data: dict | None,
    base_features: list[float],
    use_embeddings: bool = True,
    session=None,
) -> list[float]:
    """
    Extract advanced feature set (embeddings + engineered features).

    Args:
        issue: Issue dictionary from the database.
        profile_data: Optional profile context for feature generation.
        base_features: List of 14 base features.
        use_embeddings: Include text embeddings when True.
        session: Optional SQLAlchemy session for embedding caching.

    Returns:
        List of 193 advanced features combining embeddings and engineered values.
    """
    advanced_features = []

    # Text embeddings (100 + 50 = 150 features)
    if use_embeddings:
        try:
            description_emb, title_emb = get_text_embeddings(issue, session=session)

            # For now, use first 100 dims of description and first 50 dims of title
            # PCA projection will be applied during training
            desc_len = len(description_emb)
            title_len = len(title_emb)
            desc_reduced = (
                description_emb[:100]
                if desc_len >= 100
                else np.pad(description_emb, (0, 100 - desc_len))
            )
            title_reduced = (
                title_emb[:50] if title_len >= 50 else np.pad(title_emb, (0, 50 - title_len))
            )

            advanced_features.extend(desc_reduced.tolist())
            advanced_features.extend(title_reduced.tolist())
        except Exception:
            # Fallback: zero embeddings if generation fails
            advanced_features.extend([0.0] * 150)
    else:
        advanced_features.extend([0.0] * 150)

    # Interaction features (12)
    interaction_features = extract_interaction_features(base_features)
    advanced_features.extend(interaction_features)

    # Polynomial features (27)
    polynomial_features = extract_polynomial_features(base_features)
    advanced_features.extend(polynomial_features)

    # Temporal features (4) - return only first 4
    temporal_features = extract_temporal_features(issue)
    advanced_features.extend(temporal_features[:4])

    return advanced_features
