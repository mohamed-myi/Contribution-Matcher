import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from core.constants import KEYWORD_SKILLS, POPULAR_LANGUAGES, SKILL_CATEGORIES


def _normalize(text: str) -> str:
    return text.lower()


def _count_keyword_occurrences(text: str) -> Dict[str, int]:
    """
    Count occurrences of each known skill keyword in the text.
    Uses regex word boundaries to ensure whole-word matching only.
    This prevents false positives like "go" matching in "go with" or "go to".
    Prioritizes popular languages with higher weights.
    """
    text_norm = _normalize(text)
    counts: Dict[str, int] = {}
    popular_languages_lower = [lang.lower() for lang in POPULAR_LANGUAGES]
    
    for keyword in KEYWORD_SKILLS:
        needle = keyword.lower()
        
        # Escape special regex characters in the keyword
        escaped = re.escape(needle)
        
        # Use word boundaries to ensure whole-word matching
        # \b matches word boundaries (between word and non-word characters)
        # This ensures "go" only matches as a standalone word, not in "go with"
        pattern = r'\b' + escaped + r'\b'
        
        matches = re.findall(pattern, text_norm, re.IGNORECASE)
        freq = len(matches)
        
        if freq > 0:
            # Weight popular languages higher (2x multiplier)
            if needle in popular_languages_lower:
                freq = freq * 2
            counts[needle] = freq
    
    return counts


def _derive_job_category(keyword_counts: Dict[str, int]) -> Optional[str]:
    """
    Choose a single primary job category based on which category's skills
    appear most often in the description.
    """
    category_scores: Dict[str, int] = {}
    for category, skills in SKILL_CATEGORIES.items():
        score = 0
        for skill in skills:
            key = skill.lower()
            score += keyword_counts.get(key, 0)
        if score > 0:
            category_scores[category] = score

    if not category_scores:
        return None

    # Category with highest score wins
    return max(category_scores.items(), key=lambda kv: kv[1])[0]


def _extract_skills_from_counts(
    keyword_counts: Dict[str, int]
) -> List[Tuple[str, Optional[str]]]:
    """
    From keyword counts, build a list of (skill, skill_category).
    """
    skills: List[Tuple[str, Optional[str]]] = []
    for category, category_skills in SKILL_CATEGORIES.items():
        for skill in category_skills:
            key = skill.lower()
            if keyword_counts.get(key, 0) > 0:
                skills.append((skill, category))
    return skills


def analyze_job_text(
    text: str,
) -> Tuple[Optional[str], List[Tuple[str, Optional[str]]], Dict[str, int]]:
    """
    High-level API used by the job alerts script.

    Returns:
        job_category: primary category for the job (e.g., 'frontend', 'backend', ...)
        skills: list of (skill, skill_category)
        keyword_counts: mapping of keyword -> frequency in text
    """
    if not text:
        return None, [], {}

    keyword_counts = _count_keyword_occurrences(text)
    job_category = _derive_job_category(keyword_counts)
    skills = _extract_skills_from_counts(keyword_counts)
    return job_category, skills, keyword_counts


