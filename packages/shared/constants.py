"""
Shared Constants.

Constants used across all packages. These are extracted from core.constants
for shared access.
"""

from typing import Dict, List, Set

# =============================================================================
# Experience and Difficulty
# =============================================================================

EXPERIENCE_LEVELS: List[str] = ["beginner", "intermediate", "advanced"]
DIFFICULTY_LEVELS: List[str] = ["beginner", "intermediate", "advanced"]

# =============================================================================
# Issue Types
# =============================================================================

ISSUE_TYPES: List[str] = [
    "bug",
    "feature",
    "documentation",
    "testing",
    "refactoring",
    "enhancement",
    "question",
    "other",
]

CODE_FOCUSED_TYPES: Set[str] = {"bug", "feature", "refactoring", "testing"}

# =============================================================================
# Scoring Weights
# =============================================================================

SKILL_MATCH_WEIGHT: float = 40.0
EXPERIENCE_MATCH_WEIGHT: float = 20.0
REPO_QUALITY_WEIGHT: float = 15.0
FRESHNESS_WEIGHT: float = 10.0
TIME_MATCH_WEIGHT: float = 10.0
INTEREST_MATCH_WEIGHT: float = 5.0

# =============================================================================
# Technology Families
# =============================================================================

TECHNOLOGY_FAMILIES: Dict[str, List[str]] = {
    "javascript": [
        "javascript", "js", "typescript", "ts", "node", "nodejs",
        "react", "reactjs", "vue", "vuejs", "angular", "angularjs",
        "express", "expressjs", "next", "nextjs", "nuxt", "nuxtjs",
        "svelte", "deno", "bun",
    ],
    "python": [
        "python", "py", "django", "flask", "fastapi",
        "numpy", "pandas", "scipy", "scikit-learn", "sklearn",
        "tensorflow", "pytorch", "keras", "celery",
    ],
    "java": [
        "java", "kotlin", "spring", "springboot", "spring-boot",
        "maven", "gradle", "jvm", "scala",
    ],
    "go": ["go", "golang"],
    "rust": ["rust", "rs"],
    "ruby": ["ruby", "rb", "rails", "ruby-on-rails"],
    "php": ["php", "laravel", "symfony", "wordpress"],
    "csharp": ["c#", "csharp", "dotnet", ".net", "asp.net"],
    "cpp": ["c++", "cpp", "c"],
    "swift": ["swift", "ios", "swiftui"],
    "database": [
        "sql", "mysql", "postgresql", "postgres", "sqlite",
        "mongodb", "redis", "elasticsearch", "cassandra",
        "dynamodb", "firestore",
    ],
    "cloud": [
        "aws", "gcp", "azure", "cloud", "kubernetes", "k8s",
        "docker", "terraform", "ansible", "cloudformation",
    ],
    "frontend": [
        "html", "css", "sass", "scss", "less",
        "webpack", "vite", "rollup", "parcel",
        "tailwind", "tailwindcss", "bootstrap",
    ],
    "mobile": [
        "android", "ios", "react-native", "flutter", "dart",
        "xamarin", "cordova", "ionic",
    ],
    "devops": [
        "ci/cd", "jenkins", "github-actions", "gitlab-ci",
        "circleci", "travis", "devops", "sre",
    ],
}

# =============================================================================
# Technology Synonyms
# =============================================================================

TECHNOLOGY_SYNONYMS: Dict[str, List[str]] = {
    "javascript": ["js", "ecmascript"],
    "typescript": ["ts"],
    "python": ["py"],
    "golang": ["go"],
    "postgresql": ["postgres", "pg"],
    "mongodb": ["mongo"],
    "kubernetes": ["k8s"],
    "react": ["reactjs", "react.js"],
    "vue": ["vuejs", "vue.js"],
    "angular": ["angularjs", "angular.js"],
    "node": ["nodejs", "node.js"],
    "next": ["nextjs", "next.js"],
    "nuxt": ["nuxtjs", "nuxt.js"],
    "express": ["expressjs", "express.js"],
    "fastapi": ["fast-api"],
    "flask": ["flask"],
    "django": ["django"],
    "rails": ["ruby-on-rails", "ror"],
    "spring": ["springboot", "spring-boot"],
    "dotnet": [".net", "asp.net"],
    "csharp": ["c#"],
    "cpp": ["c++"],
}

# =============================================================================
# GitHub API
# =============================================================================

GITHUB_API_BASE: str = "https://api.github.com"

GOOD_FIRST_ISSUE_LABELS: List[str] = [
    "good first issue",
    "good-first-issue",
    "beginner",
    "beginner-friendly",
    "first-timers-only",
    "easy",
    "starter",
    "low-hanging-fruit",
    "up-for-grabs",
    "help wanted",
    "contributions welcome",
]

# =============================================================================
# Cache Configuration
# =============================================================================

CACHE_TTL_SHORT: int = 300  # 5 minutes
CACHE_TTL_MEDIUM: int = 1800  # 30 minutes
CACHE_TTL_LONG: int = 3600  # 1 hour
CACHE_TTL_DAY: int = 86400  # 24 hours

# =============================================================================
# Rate Limiting
# =============================================================================

RATE_LIMIT_DEFAULT: int = 100  # requests per minute
RATE_LIMIT_SCORING: int = 20  # scoring requests per minute
RATE_LIMIT_DISCOVERY: int = 10  # discovery requests per minute

# =============================================================================
# Pagination
# =============================================================================

DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
