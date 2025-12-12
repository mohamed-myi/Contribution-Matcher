# Contribution Matcher

A tool that discovers GitHub issues and matches them to developer skills using hybrid scoring (rule-based + ML). Built with a React frontend and FastAPI backend.

## Quick Start

```bash
git clone <repo-url> && cd contribution_matcher
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your credentials

# Backend
uvicorn backend.app.main:app --reload

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Visit http://localhost:5173

## Features

### Core Functionality
- **GitHub OAuth** - Secure authentication via GitHub
- **Issue Discovery** - Finds "good first issue" and "help wanted" issues from GitHub
- **Smart Matching** - Scores issues based on skills, experience, interests, and repository quality
- **ML Training** - Train a personalized model from labeled issue preferences
- **Profile Sources** - Create profile from GitHub repos, resume PDF, or manual entry
- **Staleness Tracking** - Monitors issue freshness and marks closed issues

### User Experience
- **First Login Prompt** - New users prompted to sync profile from GitHub
- **Auto-Resync** - GitHub-sourced profiles automatically resync on login
- **Bookmarks and Notes** - Save and annotate issues of interest
- **Issue Labeling** - Mark issues as good/bad matches to train the ML model

## Architecture

```
contribution_matcher/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── routers/         # API endpoints (auth, issues, profile, scoring, ml, jobs)
│   │   ├── services/        # Business logic layer
│   │   ├── scheduler/       # APScheduler for background jobs
│   │   └── auth/            # JWT and GitHub OAuth
│   └── alembic/             # Database migrations
├── core/                    # Shared business logic
│   ├── api/                 # GitHub API client
│   ├── cache/               # Redis caching layer
│   ├── models/              # SQLAlchemy ORM models
│   ├── repositories/        # Data access layer
│   ├── scoring/             # Scoring engine and ML trainer
│   ├── parsing/             # Issue parsing and skill extraction
│   ├── security/            # Encryption and rate limiting
│   └── services/            # Core services (GitHub, scoring)
├── frontend/                # React SPA
│   └── src/
│       ├── components/      # Reusable UI components
│       ├── pages/           # Page components
│       ├── context/         # Auth context
│       ├── hooks/           # Custom React hooks
│       └── api/             # API client
├── workers/                 # Celery background tasks
│   └── tasks/               # Discovery, scoring, ML, staleness tasks
└── tests/                   # Test suite
    ├── backend/             # API integration tests
    └── *.py                 # Unit tests for core modules
```

## Tech Stack

### Backend
- Python 3.10+
- FastAPI with Pydantic validation
- SQLAlchemy 2.0 ORM
- Alembic migrations
- APScheduler (in-process scheduling)
- Celery + Redis (distributed task queue)
- scikit-learn (ML models)
- structlog (structured logging)

### Frontend
- React 19
- Vite (build tool)
- TanStack Query (React Query) for server state
- React Router for navigation
- Axios for HTTP requests
- react-window for virtualized lists

### Infrastructure
- SQLite (development) / PostgreSQL (production)
- Redis (caching and task queue)
- Docker Compose for local development
- GitHub Actions for CI/CD

## Database Schema

### Core Tables

| Table | Description |
|-------|-------------|
| `users` | GitHub-authenticated users with OAuth tokens |
| `dev_profile` | Developer skills, experience level, interests, and preferences |
| `issues` | Discovered GitHub issues with repository metadata |
| `issue_technologies` | Technologies extracted from issues |
| `issue_bookmarks` | User-saved issues |
| `issue_labels` | User feedback (good/bad) for ML training |
| `issue_notes` | User notes on issues |
| `issue_feature_cache` | Cached scoring features for performance |
| `issue_embeddings` | Cached text embeddings for semantic matching |
| `user_ml_models` | Trained ML model metadata and metrics |
| `repo_metadata` | Cached repository statistics |
| `token_blacklist` | Invalidated JWT tokens |

### Key Relationships
- Users have one profile, many issues, bookmarks, and labels
- Issues have many technologies, can be bookmarked and labeled
- Each user can have multiple trained ML models

## Scoring Algorithm

### Rule-Based Scoring (100 points)

| Factor | Weight | Description |
|--------|--------|-------------|
| Skill Match | 40% | Overlap between user skills and issue technologies |
| Experience Match | 20% | Issue difficulty vs user experience level |
| Repository Quality | 15% | Stars, forks, activity, contributor count |
| Freshness | 10% | Issue age and recent repository activity |
| Time Match | 10% | Estimated time vs user availability |
| Interest Match | 5% | Repository topics vs user interests |

### ML Enhancement
- Trained on user-labeled issues (good/bad)
- Logistic regression classifier with feature vectors
- Adjusts base score based on learned preferences
- Optional heavy ML dependencies (XGBoost, sentence-transformers) via `requirements-ml.txt`

## Configuration

### Required Environment Variables
```bash
JWT_SECRET_KEY=           # Min 32 chars for token signing
GITHUB_CLIENT_ID=         # From GitHub OAuth App settings
GITHUB_CLIENT_SECRET=     # From GitHub OAuth App settings
PAT_TOKEN=                # GitHub Personal Access Token for API calls
```

### Optional Environment Variables
```bash
DATABASE_URL=sqlite:///contribution_matcher.db  # PostgreSQL for production
REDIS_HOST=localhost
REDIS_PORT=6379
TOKEN_ENCRYPTION_KEY=     # Fernet key for encrypting stored tokens
DEBUG=false
ENABLE_SCHEDULER=true     # Enable background job scheduler
```

### Generate Keys
```bash
# JWT secret
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## API Endpoints

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | GET | Initiate GitHub OAuth flow |
| `/api/auth/callback` | GET | OAuth callback handler |
| `/api/auth/me` | GET | Get current user info |
| `/api/auth/logout` | POST | Invalidate session |

### Issues
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/issues` | GET | List issues (paginated, filterable) |
| `/api/issues/discover` | POST | Discover new issues from GitHub |
| `/api/issues/stats` | GET | Issue statistics |
| `/api/issues/bookmarks` | GET | Get bookmarked issues |
| `/api/issues/{id}/bookmark` | POST/DELETE | Toggle bookmark |
| `/api/issues/{id}/notes` | GET/POST | Manage issue notes |

### Profile
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/profile` | GET | Get user profile |
| `/api/profile` | PUT | Update profile |
| `/api/profile/from-github` | POST | Create/sync profile from GitHub |
| `/api/profile/from-resume` | POST | Create profile from PDF resume |

### Scoring
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scoring/top-matches` | GET | Get best matching issues |
| `/api/scoring/{id}` | GET | Get score breakdown for an issue |
| `/api/scoring/score-all` | POST | Batch score all issues |

### ML Training
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ml/label/{id}` | POST | Label issue as good/bad |
| `/api/ml/label-status` | GET | Get labeling progress |
| `/api/ml/unlabeled-issues` | GET | Get issues to label |
| `/api/ml/train` | POST | Train ML model |
| `/api/ml/model-info` | GET | Get model metrics |

### Jobs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List scheduled jobs |
| `/api/jobs/{id}/trigger` | POST | Manually trigger a job |

## CLI Commands

```bash
python main.py discover --limit 100           # Discover issues from GitHub
python main.py list --difficulty beginner     # List discovered issues
python main.py stats                          # Show issue statistics
python main.py score --top 10                 # Score and rank issues
python main.py create-profile --github <user> # Create profile from GitHub
python main.py train-model                    # Train ML model
```

## Docker Deployment

```bash
cp .env.example .env
docker-compose up -d
docker-compose exec api alembic upgrade head
```

### Services
| Service | Description |
|---------|-------------|
| `api` | FastAPI application |
| `worker-discovery` | Issue discovery Celery worker |
| `worker-scoring` | Score computation worker |
| `worker-ml` | ML training worker |
| `scheduler` | Celery beat scheduler |
| `postgres` | PostgreSQL database |
| `redis` | Cache and message broker |

## Database Migrations

```bash
cd backend
alembic upgrade head          # Apply all migrations
alembic revision -m "desc"    # Create new migration
alembic downgrade -1          # Rollback one migration
alembic history               # View migration history
```

## Testing

```bash
pytest tests/ -v                    # Run all tests
pytest tests/backend/ -v            # Backend API tests only
pytest tests/test_scoring.py -v     # Core scoring tests
pytest tests/ -k "test_name"        # Run specific test
```

## Development

### Code Quality
```bash
ruff check .              # Linting
black .                   # Formatting
mypy core/                # Type checking
pre-commit run --all-files  # Run all pre-commit hooks
```

### CI/CD
- **CI Pipeline**: Runs on push to `test`, `develop`, `main` branches
  - Linting and formatting checks
  - Backend and frontend tests
  - Security scanning
- **CD Pipeline**: Runs on push to `main` or version tags
  - Builds application
  - Deploys to Railway (when configured)

## Performance Optimizations

### Backend
- Connection pooling for database
- Redis caching for stats and metadata (5-min TTL)
- Bulk query operations (no N+1 queries)
- Precomputed feature caching
- GZip compression for responses

### Frontend
- Lazy-loaded pages with React.lazy
- React Query caching with stale-while-revalidate
- Component memoization
- Virtualized lists for large datasets
- Link prefetching on hover

---

Note: Documentation for this project was AI-assisted.

## Credits

Developed by Mohamed Ibrahim
