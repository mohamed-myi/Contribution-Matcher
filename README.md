# Contribution Matcher
Note: The UI contains the proper name, "IssueIndex", but I only came up with that after I realized how ugly "Contribution Matcher" looked and sounded.
## Background

This project originated as a personal automation script running on GitHub Actions. Its original purpose was to passively collect job descriptions via a daily cron job, parse them, and cross-reference them with my resume to find relevant opportunities. It operated purely as a backend utility. Once I realizedthe potential I decided to expand it into a full-stack application. The other option was to convert it to a dating app, but I can't see a way to get enough users/data to make it viable.

I wanted to create a more advanced model and needed a source of real human data that was realistically being sourced and had a reasonable amount of randomness. I wanted to try solving a real problem instead of testing proven algorithms on curated data. Job descriptions tend to have a pretty consistent format, so that model produced a high precision score quickly. The model and architecture are intentionally overdone from just progressively experimenting with different frameworks and choosing to integrate instead of using a monolithic framework.

*   **Distributed Systems**: Implementing Celery and Redis to handle asynchronous ingestion and processing.
*   **Machine Learning**: Building and integrating custom scoring models from scratch.
*   **Clean Architecture**: Enforcing strict separation of concerns to practice domain-driven design patterns.

The backend was built prior to the current product idea, which led to some complex database migrations and distinct architectural choices. I have spent significant time refining these components, and the project is now intended for portfolio purposes to demonstrate full-stack engineering and distributed system capabilities.

## Highlights

*   **Distributed Architecture**: Decoupled ingestion and scoring pipelines using Celery & Redis for robust background processing.
*   **Clean Architecture**: Strict separation between core business logic, API layers, and data repositories to mock real-world enterprise patterns.
*   **Hybrid ML Scoring**: Combining rule-based heuristics with logistic regression for customized, learned recommendations.
*   **Full Stack Integration**: End-to-end type safety and state management with FastAPI and React 19.

## Tech Stack

### Backend
*   **FastAPI**: High-performance async API.
*   **Celery + Redis**: Distributed task queue for ingestion and scoring.
*   **Alembic**: Complex database migration management.
*   **Scikit-learn**: Logic regression models for issue scoring.
*   **APScheduler**: In-process scheduling for maintenance tasks.

### Frontend
*   **React 19**: Latest React features.
*   **TanStack Query**: Server state management and caching.
*   **Vitest**: Modern, fast unit testing.
*   **Vite**: Next-generation frontend tooling.

---

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
- Trained on user-labeled issues (like/dislike)
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
DATABASE_URL=sqlite:///contribution_matcher.db  # Tested with SQLite and PostgreSQL for production
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

Note: Documentation was AI-assisted, but guided and reviewed thoroughly by myself.

## Credits

By Mohamed Ibrahim.
