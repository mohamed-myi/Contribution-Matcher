'''
Advanced Feature Extraction Module

This module extracts advanced features for ML training, including:
- Text embeddings (BERT) for issue descriptions and titles
- Interaction features between base features
- Polynomial feature expansion
- Temporal features (freshness, days since creation)
'''

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.preprocessing import PolynomialFeatures

from core.database import get_issue_embedding, upsert_issue_embedding


# Global embedding model (lazy loaded)
_embedding_model = None
_embedding_model_name = 'all-MiniLM-L6-v2'


def _get_embedding_model():
    '''
    Lazy load the sentence transformer model.
    
    Returns - The loaded SentenceTransformer model
    '''
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


def get_text_embeddings(issue: Dict) -> Tuple[np.ndarray, np.ndarray]:
    '''
    Generate BERT embeddings for issue description and title.
    Uses cached embeddings from database if available.
    
    Args:
        issue: Issue dictionary from database
        
    Returns:
        Tuple of (description_embedding, title_embedding) - both 384-dimensional arrays
    '''
    issue_id = issue.get('id')
    
    # Try to load from cache
    if issue_id:
        cached = get_issue_embedding(issue_id)
        if cached is not None:
            return cached
    
    # Generate embeddings
    model = _get_embedding_model()
    
    # Get text content
    description = issue.get('body', '') or ''
    title = issue.get('title', '') or ''
    
    # Generate embeddings (384 dimensions each)
    description_embedding = model.encode(description, convert_to_numpy=True)
    title_embedding = model.encode(title, convert_to_numpy=True)
    
    # Cache in database
    if issue_id:
        upsert_issue_embedding(issue_id, description_embedding, title_embedding, _embedding_model_name)
    
    return description_embedding, title_embedding


def extract_interaction_features(base_features: List[float]) -> List[float]:
    '''
    Extract interaction features between key base features.
    
    Args:
        base_features: List of 14 base features
        
    Returns:
        List of 12 interaction features
    '''
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


def extract_polynomial_features(base_features: List[float]) -> List[float]:
    '''
    Extract polynomial features (degree 2) from key numeric features.
    
    Args:
        base_features: List of base features
        
    Returns:
        List of 27 polynomial features (6 original + 6 squared + 15 cross-products)
    '''
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
    '''
    Parse a date value and return days since that date.
    
    Args:
        date_value: Date string or datetime object
        default_days: Default days to return if parsing fails
        
    Returns:
        Days since the date
    '''
    if not date_value:
        return default_days
    
    try:
        if isinstance(date_value, str):
            date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
        else:
            date_obj = date_value
        days = (datetime.now() - date_obj.replace(tzinfo=None)).days
        return float(days)
    except (ValueError, AttributeError, TypeError):
        return default_days


def extract_temporal_features(issue: Dict) -> List[float]:
    '''
    Extract temporal features based on issue creation and update dates.
    
    Args:
        issue: Issue dictionary from database
        
    Returns:
        List of 5 temporal features
    '''
    days_since_created = _parse_date_to_days(issue.get('created_at'))
    days_since_updated = _parse_date_to_days(issue.get('updated_at'))
    
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
    issue: Dict,
    profile_data: Optional[Dict],
    base_features: List[float],
    use_embeddings: bool = True,
) -> List[float]:
    '''
    Extract all advanced features (193 total).
    
    Args:
        issue: Issue dictionary from database
        profile_data: Optional profile data
        base_features: List of 14 base features
        use_embeddings: Whether to include text embeddings (default: True)
        
    Returns:
        List of 193 advanced features:
        - Text embeddings: 100 (PCA-reduced description embeddings)
        - Title embeddings: 50 (PCA-reduced title embeddings)
        - Interaction features: 12
        - Polynomial features: 27
        - Temporal features: 4
    '''
    advanced_features = []
    
    # Text embeddings (100 + 50 = 150 features)
    if use_embeddings:
        try:
            description_emb, title_emb = get_text_embeddings(issue)
            
            # For now, use first 100 dims of description and first 50 dims of title
            # PCA projection will be applied during training
            desc_len = len(description_emb)
            title_len = len(title_emb)
            desc_reduced = description_emb[:100] if desc_len >= 100 else np.pad(description_emb, (0, 100 - desc_len))
            title_reduced = title_emb[:50] if title_len >= 50 else np.pad(title_emb, (0, 50 - title_len))
            
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

