SKILL_CATEGORIES = {
    "frontend": [
        "javascript",
        "typescript",
        "react",
        "vue",
        "angular",
        "html",
        "css",
        "tailwind",
        "next.js",
        "nextjs",
        "svelte",
        "webpack",
        "redux",
        "vue.js",
        "angularjs",
        "jquery",
        "sass",
        "scss",
        "less",
        "bootstrap",
        "material-ui",
        "mui",
        "styled-components",
        "emotion",
        "storybook",
        "jest",
        "vitest",
        "cypress",
        "playwright",
        "webdriver",
        "responsive design",
        "accessibility",
        "a11y",
        "pwa",
        "progressive web app",
        "webpack",
        "vite",
        "esbuild",
        "rollup",
        "parcel",
    ],
    "backend": [
        "python",
        "django",
        "flask",
        "fastapi",
        "java",
        "spring",
        "spring boot",
        "c#",
        ".net",
        "node",
        "node.js",
        "nodejs",
        "express",
        "go",
        "golang",
        "ruby",
        "rails",
        "c++",
        "cpp",
        "c",
        "rust",
        "swift",
        "kotlin",
        "php",
        "scala",
        "graphql",
        "rest api",
        "rest",
        "api",
        "microservices",
        "serverless",
        "gin",
        "echo",
        "fiber",
        "actix",
        "rocket",
        "sinatra",
        "tornado",
        "aiohttp",
        "asyncio",
        "celery",
        "rq",
        "grpc",
        "websocket",
        "socket.io",
        "message queue",
        "rabbitmq",
        "activemq",
        "apache kafka",
        "kafka",
    ],
    "fullstack": [
        "full stack",
        "full-stack",
        "fullstack",
    ],
    "data": [
        "sql",
        "postgresql",
        "mysql",
        "mongodb",
        "pandas",
        "numpy",
        "data engineer",
        "data scientist",
        "data science",
        "spark",
        "redis",
        "elasticsearch",
        "cassandra",
        "dynamodb",
        "nosql",
        "data warehouse",
        "etl",
        "airflow",
        "kafka",
        "hadoop",
        "hive",
        "presto",
        "trino",
        "clickhouse",
        "snowflake",
        "bigquery",
        "redshift",
        "databricks",
        "dbt",
        "tableau",
        "power bi",
        "looker",
        "superset",
        "metabase",
        "sqlite",
        "oracle",
        "sql server",
        "mariadb",
        "couchdb",
        "neo4j",
        "influxdb",
        "timescaledb",
        "data modeling",
        "data pipeline",
        "data lake",
    ],
    "ml_ai": [
        "machine learning",
        "deep learning",
        "pytorch",
        "tensorflow",
        "scikit-learn",
        "sklearn",
        "ml engineer",
        "ai engineer",
        "llm",
        "large language model",
        "transformer",
        "neural network",
        "nlp",
        "natural language processing",
        "computer vision",
        "reinforcement learning",
        "gpu",
        "cuda",
        "keras",
        "jax",
        "hugging face",
        "transformers",
        "openai",
        "langchain",
        "llama",
        "gpt",
        "bert",
        "lstm",
        "cnn",
        "rnn",
        "gan",
        "svm",
        "random forest",
        "xgboost",
        "lightgbm",
        "catboost",
        "feature engineering",
        "model deployment",
        "mlops",
        "model serving",
        "triton",
        "onnx",
        "tensorrt",
        "opencv",
        "nltk",
        "spacy",
        "gensim",
        "prompt engineering",
    ],
    "security": [
        "security engineer",
        "application security",
        "appsec",
        "infosec",
        "information security",
        "soc",
        "siem",
        "threat detection",
        "incident response",
        "penetration testing",
        "pentest",
        "vulnerability management",
        "devsecops",
        "owasp",
        "cryptography",
        "encryption",
        "authentication",
        "authorization",
        "oauth",
        "jwt",
        "saml",
        "ldap",
        "rbac",
        "zero trust",
        "firewall",
        "ids",
        "ips",
        "waf",
        "dns security",
        "ssl",
        "tls",
        "certificate management",
        "secrets management",
        "vault",
        "hashiCorp vault",
        "burp suite",
        "metasploit",
        "nmap",
        "wireshark",
        "security audit",
        "compliance",
        "gdpr",
        "hipaa",
        "pci dss",
        "iso 27001",
    ],
    "devops": [
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "terraform",
        "ci/cd",
        "lambda",
        "s3",
        "ec2",
        "jenkins",
        "github actions",
        "gitlab ci",
        "ansible",
        "chef",
        "puppet",
        "prometheus",
        "grafana",
        "linux",
        "unix",
        "bash",
        "shell scripting",
        "git",
        "helm",
        "istio",
        "linkerd",
        "argo",
        "flux",
        "spinnaker",
        "circleci",
        "travis ci",
        "bamboo",
        "teamcity",
        "cloudformation",
        "pulumi",
        "packer",
        "vagrant",
        "consul",
        "nomad",
        "vault",
        "nginx",
        "apache",
        "haproxy",
        "kong",
        "envoy",
        "datadog",
        "new relic",
        "splunk",
        "elk stack",
        "elastic stack",
        "loki",
        "jaeger",
        "zipkin",
        "monitoring",
        "observability",
        "apm",
        "distributed tracing",
    ],
    "systems": [
        "multithreading",
        "concurrency",
        "parallel computing",
        "distributed systems",
        "operating systems",
        "system design",
        "performance optimization",
        "memory management",
        "cpu optimization",
        "cache",
        "caching",
        "load balancing",
        "scalability",
        "high availability",
        "fault tolerance",
        "disaster recovery",
        "backup",
        "replication",
        "sharding",
        "partitioning",
        "consensus algorithms",
        "raft",
        "paxos",
        "event sourcing",
        "cqrs",
        "message broker",
        "queue",
        "pub/sub",
        "stream processing",
    ],
}


# For now, we treat all of the above skills as the keyword universe we care about.
KEYWORD_SKILLS = sorted(
    {skill.lower() for skills in SKILL_CATEGORIES.values() for skill in skills}
)


# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
RATE_LIMIT_REQUESTS_PER_HOUR = 5000  # Authenticated limit

# Issue search labels
GOOD_FIRST_ISSUE_LABELS = ["good first issue", "good-first-issue", "beginner-friendly", "beginner friendly"]
HELP_WANTED_LABELS = ["help wanted", "help-wanted"]

# Expanded discovery labels for variety
DISCOVERY_LABELS = [
    # Beginner-friendly
    "good first issue",
    "good-first-issue",
    "beginner",
    "beginner-friendly",
    "first-timers-only",
    "easy",
    "starter",
    "newbie",
    "low-hanging-fruit",
    # Help wanted
    "help wanted",
    "help-wanted",
    "contributions welcome",
    "up-for-grabs",
    # Issue types
    "bug",
    "enhancement",
    "feature",
    "documentation",
    "docs",
    # Community events
    "hacktoberfest",
    "hacktoberfest-accepted",
]

# Languages to rotate through for discovery variety
DISCOVERY_LANGUAGES = [
    "python",
    "javascript", 
    "typescript",
    "go",
    "rust",
    "java",
    "ruby",
    "c++",
    "swift",
    "kotlin",
    "php",
    "c#",
    "scala",
    "elixir",
]

# Technology synonyms and relationships for semantic matching
TECHNOLOGY_SYNONYMS = {
    # JavaScript variations
    "javascript": ["js", "ecmascript", "node", "node.js", "nodejs"],
    "typescript": ["ts"],
    "js": ["javascript", "ecmascript"],
    "node": ["node.js", "nodejs", "javascript"],
    "node.js": ["node", "nodejs", "javascript"],
    "nodejs": ["node", "node.js", "javascript"],
    
    # Python variations
    "python": ["py", "python3", "python2"],
    "py": ["python", "python3"],
    
    # React ecosystem
    "react": ["reactjs", "react.js"],
    "react native": ["react-native", "rn"],
    "next.js": ["nextjs", "next"],
    "nextjs": ["next.js", "next"],
    
    # Vue ecosystem
    "vue": ["vue.js", "vuejs"],
    "vue.js": ["vue", "vuejs"],
    
    # Angular ecosystem
    "angular": ["angularjs", "angular.js"],
    "angularjs": ["angular", "angular.js"],
    
    # CSS variations
    "css": ["css3"],
    "sass": ["scss"],
    "scss": ["sass"],
    
    # Go variations
    "go": ["golang"],
    "golang": ["go"],
    
    # C++ variations
    "c++": ["cpp", "cplusplus"],
    "cpp": ["c++", "cplusplus"],
    
    # .NET variations
    "c#": [".net", "dotnet", "csharp"],
    ".net": ["c#", "dotnet", "csharp"],
    "dotnet": ["c#", ".net", "csharp"],
    
    # Database variations
    "postgresql": ["postgres", "pg"],
    "postgres": ["postgresql", "pg"],
    "mongodb": ["mongo"],
    "mongo": ["mongodb"],
    "mysql": ["mariadb"],
    
    # Framework relationships
    "django": ["python"],
    "flask": ["python"],
    "fastapi": ["python"],
    "express": ["node", "node.js", "javascript"],
    "rails": ["ruby"],
    "spring": ["java"],
    "spring boot": ["java", "spring"],
}

# Technology families (related technologies)
TECHNOLOGY_FAMILIES = {
    "react": ["react", "react native", "reactjs", "next.js", "nextjs"],
    "vue": ["vue", "vue.js", "vuejs", "nuxt", "nuxt.js"],
    "angular": ["angular", "angularjs", "angular.js"],
    "python": ["python", "django", "flask", "fastapi", "tornado"],
    "javascript": ["javascript", "typescript", "node", "node.js", "react", "vue", "angular"],
    "java": ["java", "spring", "spring boot", "kotlin"],
    "go": ["go", "golang"],
    "rust": ["rust"],
    "c++": ["c++", "cpp", "c"],
}

# Popular languages (for prioritization)
POPULAR_LANGUAGES = [
    "python", "javascript", "typescript", "java", "go", "rust", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "scala", "dart", "r", "matlab"
]

# Code-focused issue types (for prioritization)
CODE_FOCUSED_TYPES = ["bug", "feature", "refactoring"]

# Scoring weights
SKILL_MATCH_WEIGHT = 40
EXPERIENCE_MATCH_WEIGHT = 20
REPO_QUALITY_WEIGHT = 15
FRESHNESS_WEIGHT = 10
TIME_MATCH_WEIGHT = 10
INTEREST_MATCH_WEIGHT = 5


# =============================================================================
# APPLICATION SETTINGS (Pydantic)
# =============================================================================

from functools import lru_cache
from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Unified application settings.
    
    Merges configuration from:
    - backend/app/config.py (API settings)
    - Environment variables
    - .env file
    
    Usage:
        from core.config import get_settings
        settings = get_settings()
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Contribution Matcher"
    api_prefix: str = "/api"
    debug: bool = Field(default=False)

    # Database
    database_url: str = Field(
        default="sqlite:///contribution_matcher.db",
        validation_alias="DATABASE_URL",
    )
    
    # Database Pool Settings (for PostgreSQL)
    db_pool_size: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    db_pool_pre_ping: bool = Field(default=True, validation_alias="DB_POOL_PRE_PING")

    # GitHub OAuth
    github_client_id: str = Field(default="", validation_alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(default="", validation_alias="GITHUB_CLIENT_SECRET")
    github_redirect_uri: Optional[AnyHttpUrl] = Field(
        default=None,
        validation_alias="GITHUB_REDIRECT_URI",
    )
    github_scope: str = Field(default="read:user user:email")
    
    # GitHub API (for CLI/discovery)
    pat_token: Optional[str] = Field(default=None, validation_alias="PAT_TOKEN")

    # JWT Authentication
    jwt_secret_key: str = Field(default="CHANGE_ME", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60 * 24)  # 1 day
    
    # Security
    token_encryption_key: Optional[str] = Field(
        default=None,
        validation_alias="TOKEN_ENCRYPTION_KEY",
        description="Fernet key for encrypting stored tokens (generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')",
    )
    require_encryption: bool = Field(
        default=False,
        validation_alias="REQUIRE_ENCRYPTION",
        description="If True, fail startup if encryption key is not set",
    )
    strict_security: bool = Field(
        default=False,
        validation_alias="STRICT_SECURITY",
        description="If True, fail startup on any security warnings",
    )
    
    # Rate Limiting
    auth_rate_limit: int = Field(default=5, validation_alias="AUTH_RATE_LIMIT")
    auth_rate_window: int = Field(default=300, validation_alias="AUTH_RATE_WINDOW")  # 5 minutes
    api_rate_limit: int = Field(default=100, validation_alias="API_RATE_LIMIT")
    api_rate_window: int = Field(default=60, validation_alias="API_RATE_WINDOW")  # 1 minute

    # CORS
    cors_allowed_origins: str = Field(
        default="http://localhost:5173",
        validation_alias="CORS_ALLOWED_ORIGINS",
    )

    # Redis (for caching - Phase 2)
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, validation_alias="REDIS_PASSWORD")
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Celery (for background tasks - Phase 3)
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        validation_alias="CELERY_RESULT_BACKEND",
    )

    # Scheduler
    enable_scheduler: bool = Field(default=False, validation_alias="ENABLE_SCHEDULER")
    scheduler_discovery_cron: str = Field(
        default="0 6 * * *",
        validation_alias="SCHEDULER_DISCOVERY_CRON",
    )
    scheduler_scoring_cron: str = Field(
        default="30 6 * * *",
        validation_alias="SCHEDULER_SCORING_CRON",
    )
    scheduler_ml_cron: str = Field(
        default="0 7 * * *",
        validation_alias="SCHEDULER_ML_CRON",
    )
    scheduler_discovery_limit: int = Field(
        default=50,
        validation_alias="SCHEDULER_DISCOVERY_LIMIT",
    )
    
    # Discovery settings
    fast_discovery: bool = Field(default=True, validation_alias="FAST_DISCOVERY")
    cache_validity_days: int = Field(default=7, validation_alias="CACHE_VALIDITY_DAYS")


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses LRU cache to avoid re-reading environment on every call.
    """
    return Settings()

