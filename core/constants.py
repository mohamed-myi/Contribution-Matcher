"""
Application constants for Contribution Matcher.

Contains skill categories, technology mappings, and scoring weights.
"""

# =============================================================================
# Skill Categories
# =============================================================================

SKILL_CATEGORIES = {
    "frontend": [
        "javascript", "typescript", "react", "vue", "angular", "html", "css",
        "tailwind", "next.js", "nextjs", "svelte", "webpack", "redux", "vue.js",
        "angularjs", "jquery", "sass", "scss", "less", "bootstrap", "material-ui",
        "mui", "styled-components", "emotion", "storybook", "jest", "vitest",
        "cypress", "playwright", "webdriver", "responsive design", "accessibility",
        "a11y", "pwa", "progressive web app", "vite", "esbuild", "rollup", "parcel",
    ],
    "backend": [
        "python", "django", "flask", "fastapi", "java", "spring", "spring boot",
        "c#", ".net", "node", "node.js", "nodejs", "express", "go", "golang",
        "ruby", "rails", "c++", "cpp", "c", "rust", "swift", "kotlin", "php",
        "scala", "graphql", "rest api", "rest", "api", "microservices", "serverless",
        "gin", "echo", "fiber", "actix", "rocket", "sinatra", "tornado", "aiohttp",
        "asyncio", "celery", "rq", "grpc", "websocket", "socket.io", "message queue",
        "rabbitmq", "activemq", "apache kafka", "kafka",
    ],
    "fullstack": ["full stack", "full-stack", "fullstack"],
    "data": [
        "sql", "postgresql", "mysql", "mongodb", "pandas", "numpy", "data engineer",
        "data scientist", "data science", "spark", "redis", "elasticsearch",
        "cassandra", "dynamodb", "nosql", "data warehouse", "etl", "airflow",
        "kafka", "hadoop", "hive", "presto", "trino", "clickhouse", "snowflake",
        "bigquery", "redshift", "databricks", "dbt", "tableau", "power bi",
        "looker", "superset", "metabase", "sqlite", "oracle", "sql server",
        "mariadb", "couchdb", "neo4j", "influxdb", "timescaledb", "data modeling",
        "data pipeline", "data lake",
    ],
    "ml_ai": [
        "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn",
        "sklearn", "ml engineer", "ai engineer", "llm", "large language model",
        "transformer", "neural network", "nlp", "natural language processing",
        "computer vision", "reinforcement learning", "gpu", "cuda", "keras", "jax",
        "hugging face", "transformers", "openai", "langchain", "llama", "gpt",
        "bert", "lstm", "cnn", "rnn", "gan", "svm", "random forest", "xgboost",
        "lightgbm", "catboost", "feature engineering", "model deployment", "mlops",
        "model serving", "triton", "onnx", "tensorrt", "opencv", "nltk", "spacy",
        "gensim", "prompt engineering",
    ],
    "security": [
        "security engineer", "application security", "appsec", "infosec",
        "information security", "soc", "siem", "threat detection", "incident response",
        "penetration testing", "pentest", "vulnerability management", "devsecops",
        "owasp", "cryptography", "encryption", "authentication", "authorization",
        "oauth", "jwt", "saml", "ldap", "rbac", "zero trust", "firewall", "ids",
        "ips", "waf", "dns security", "ssl", "tls", "certificate management",
        "secrets management", "vault", "hashiCorp vault", "burp suite", "metasploit",
        "nmap", "wireshark", "security audit", "compliance", "gdpr", "hipaa",
        "pci dss", "iso 27001",
    ],
    "devops": [
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
        "lambda", "s3", "ec2", "jenkins", "github actions", "gitlab ci", "ansible",
        "chef", "puppet", "prometheus", "grafana", "linux", "unix", "bash",
        "shell scripting", "git", "helm", "istio", "linkerd", "argo", "flux",
        "spinnaker", "circleci", "travis ci", "bamboo", "teamcity", "cloudformation",
        "pulumi", "packer", "vagrant", "consul", "nomad", "vault", "nginx",
        "apache", "haproxy", "kong", "envoy", "datadog", "new relic", "splunk",
        "elk stack", "elastic stack", "loki", "jaeger", "zipkin", "monitoring",
        "observability", "apm", "distributed tracing",
    ],
    "systems": [
        "multithreading", "concurrency", "parallel computing", "distributed systems",
        "operating systems", "system design", "performance optimization",
        "memory management", "cpu optimization", "cache", "caching", "load balancing",
        "scalability", "high availability", "fault tolerance", "disaster recovery",
        "backup", "replication", "sharding", "partitioning", "consensus algorithms",
        "raft", "paxos", "event sourcing", "cqrs", "message broker", "queue",
        "pub/sub", "stream processing",
    ],
}

# Flattened unique skills for quick lookups
KEYWORD_SKILLS = sorted({skill.lower() for skills in SKILL_CATEGORIES.values() for skill in skills})

# =============================================================================
# GitHub API Constants
# =============================================================================

GITHUB_API_BASE = "https://api.github.com"
GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
RATE_LIMIT_REQUESTS_PER_HOUR = 5000

# =============================================================================
# Issue Discovery Labels
# =============================================================================

GOOD_FIRST_ISSUE_LABELS = ["good first issue", "good-first-issue", "beginner-friendly", "beginner friendly"]
HELP_WANTED_LABELS = ["help wanted", "help-wanted"]

DISCOVERY_LABELS = [
    "good first issue", "good-first-issue", "beginner", "beginner-friendly",
    "first-timers-only", "easy", "starter", "newbie", "low-hanging-fruit",
    "help wanted", "help-wanted", "contributions welcome", "up-for-grabs",
    "bug", "enhancement", "feature", "documentation", "docs",
    "hacktoberfest", "hacktoberfest-accepted",
]

DISCOVERY_LANGUAGES = [
    "python", "javascript", "typescript", "go", "rust", "java",
    "ruby", "c++", "swift", "kotlin", "php", "c#", "scala", "elixir",
]

# =============================================================================
# Technology Mappings
# =============================================================================

TECHNOLOGY_SYNONYMS = {
    "javascript": ["js", "ecmascript", "node", "node.js", "nodejs"],
    "typescript": ["ts"],
    "js": ["javascript", "ecmascript"],
    "node": ["node.js", "nodejs", "javascript"],
    "node.js": ["node", "nodejs", "javascript"],
    "nodejs": ["node", "node.js", "javascript"],
    "python": ["py", "python3", "python2"],
    "py": ["python", "python3"],
    "react": ["reactjs", "react.js"],
    "react native": ["react-native", "rn"],
    "next.js": ["nextjs", "next"],
    "nextjs": ["next.js", "next"],
    "vue": ["vue.js", "vuejs"],
    "vue.js": ["vue", "vuejs"],
    "angular": ["angularjs", "angular.js"],
    "angularjs": ["angular", "angular.js"],
    "css": ["css3"],
    "sass": ["scss"],
    "scss": ["sass"],
    "go": ["golang"],
    "golang": ["go"],
    "c++": ["cpp", "cplusplus"],
    "cpp": ["c++", "cplusplus"],
    "c#": [".net", "dotnet", "csharp"],
    ".net": ["c#", "dotnet", "csharp"],
    "dotnet": ["c#", ".net", "csharp"],
    "postgresql": ["postgres", "pg"],
    "postgres": ["postgresql", "pg"],
    "mongodb": ["mongo"],
    "mongo": ["mongodb"],
    "mysql": ["mariadb"],
    "django": ["python"],
    "flask": ["python"],
    "fastapi": ["python"],
    "express": ["node", "node.js", "javascript"],
    "rails": ["ruby"],
    "spring": ["java"],
    "spring boot": ["java", "spring"],
}

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

POPULAR_LANGUAGES = [
    "python", "javascript", "typescript", "java", "go", "rust", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "scala", "dart", "r", "matlab"
]

# =============================================================================
# Scoring Weights
# =============================================================================

CODE_FOCUSED_TYPES = ["bug", "feature", "refactoring"]

SKILL_MATCH_WEIGHT = 40
EXPERIENCE_MATCH_WEIGHT = 20
REPO_QUALITY_WEIGHT = 15
FRESHNESS_WEIGHT = 10
TIME_MATCH_WEIGHT = 10
INTEREST_MATCH_WEIGHT = 5

__all__ = [
    "SKILL_CATEGORIES",
    "KEYWORD_SKILLS",
    "GITHUB_API_BASE",
    "GITHUB_GRAPHQL_ENDPOINT",
    "RATE_LIMIT_REQUESTS_PER_HOUR",
    "GOOD_FIRST_ISSUE_LABELS",
    "HELP_WANTED_LABELS",
    "DISCOVERY_LABELS",
    "DISCOVERY_LANGUAGES",
    "TECHNOLOGY_SYNONYMS",
    "TECHNOLOGY_FAMILIES",
    "POPULAR_LANGUAGES",
    "CODE_FOCUSED_TYPES",
    "SKILL_MATCH_WEIGHT",
    "EXPERIENCE_MATCH_WEIGHT",
    "REPO_QUALITY_WEIGHT",
    "FRESHNESS_WEIGHT",
    "TIME_MATCH_WEIGHT",
    "INTEREST_MATCH_WEIGHT",
]

