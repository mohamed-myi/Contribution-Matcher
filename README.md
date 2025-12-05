# MYI - Contribution Matcher

Discovers GitHub issues and matches them to developer skills using hybrid scoring (rules + ML). Features a modern React frontend with optimized performance and a FastAPI backend with Redis caching.

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

### Core
- **GitHub OAuth** - Secure authentication via GitHub
- **Issue Discovery** - Find "good first issue" and "help wanted" issues
- **Smart Matching** - Score issues based on skills, experience, and interests
- **Algorithm Training** - Train a personalized model from labeled preferences
- **Profile Sources** - Create profile from GitHub repos, resume PDF, or manually
- **Profile Tracking** - Tracks source (GitHub/Resume/Manual) with auto-resync

### User Experience
- **First Login Prompt** - New users prompted to sync profile from GitHub
- **Auto-Resync** - GitHub-sourced profiles automatically resync on login
- **Profile Source Indicator** - Shows where profile data originated
- **Confirmation Dialogs** - Warns before overwriting profile data

### Frontend (React 19 + Vite)
- **Code Splitting** - Lazy-loaded pages for faster initial load
- **React Query** - Automatic caching, deduplication, and background refresh
- **Optimized Rendering** - Memoized components and batched state updates
- **Link Prefetching** - Data loaded on hover for instant navigation
- **GZip Compression** - Compressed API responses

### Backend (FastAPI + SQLAlchemy)
- **Connection Pooling** - Efficient database connections
- **Response Caching** - Redis-backed caching for stats and metadata
- **Bulk Operations** - Optimized batch queries (no N+1)
- **Structured Logging** - JSON logs with request tracing

## Configuration

### Required
```bash
JWT_SECRET_KEY=        # Min 32 chars - python -c "import secrets; print(secrets.token_urlsafe(48))"
GITHUB_CLIENT_ID=      # From GitHub OAuth App
GITHUB_CLIENT_SECRET=  # From GitHub OAuth App
PAT_TOKEN=             # GitHub Personal Access Token
```

### Optional
```bash
DATABASE_URL=sqlite:///contribution_matcher.db  # Or PostgreSQL
REDIS_HOST=localhost
REDIS_PORT=6379
TOKEN_ENCRYPTION_KEY=  # Fernet key for secure token storage
DEBUG=false
```

### Generate Keys
```bash
# JWT secret
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## CLI Commands

```bash
python main.py discover --limit 100           # Discover issues from GitHub
python main.py list --difficulty beginner     # List discovered issues
python main.py stats                          # Show issue statistics
python main.py score --top 10                 # Score and rank issues
python main.py create-profile --github <user> # Create profile from GitHub
python main.py train-model                    # Train algorithm (200+ labels required)
```

## API Endpoints

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | GET | Initiate GitHub OAuth |
| `/api/auth/callback` | GET | OAuth callback |
| `/api/auth/me` | GET | Current user info |
| `/api/auth/logout` | POST | Invalidate session |

### Issues
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/issues` | GET | List issues (paginated, filterable) |
| `/api/issues/discover` | POST | Discover new issues |
| `/api/issues/stats` | GET | Issue statistics (cached) |
| `/api/issues/bookmarks` | GET | Bookmarked issues |
| `/api/issues/{id}/bookmark` | POST/DELETE | Toggle bookmark |
| `/api/issues/{id}/notes` | GET/POST | Issue notes |

### Profile
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/profile` | GET | Get profile (includes source info) |
| `/api/profile` | PUT | Update profile |
| `/api/profile/from-github` | POST | Create/sync from GitHub |
| `/api/profile/from-resume` | POST | Create from PDF resume |

### Algorithm Training
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ml/label/{id}` | POST | Label issue (like/dislike) |
| `/api/ml/label-status` | GET | Labeling progress |
| `/api/ml/unlabeled-issues` | GET | Issues to label |
| `/api/ml/train` | POST | Train algorithm |
| `/api/ml/model-info` | GET | Algorithm metrics |

### Scoring
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scoring/top-matches` | GET | Best matching issues |
| `/api/scoring/score-all` | POST | Batch score issues |

## Frontend Routes

| Route | Page | Description |
|-------|------|-------------|
| `/dashboard` | Dashboard | Overview, stats, quick actions |
| `/issues` | Issues | Browse and filter issues |
| `/profile` | Profile | Manage developer profile |
| `/algorithm-improvement` | Algorithm Improvement | Label issues and train algorithm |

## Docker

```bash
cp docker/env.example .env
docker-compose up -d
docker-compose exec api alembic upgrade head
```

**Services:**
- `api` - FastAPI application
- `worker-discovery` - Issue discovery worker
- `worker-scoring` - Score computation worker
- `worker-ml` - Algorithm training worker
- `scheduler` - Celery beat scheduler
- `postgres` - PostgreSQL database
- `redis` - Cache and message broker

## Scoring Algorithm

### Rule-Based (100 points)
| Factor | Weight | Description |
|--------|--------|-------------|
| Skill Match | 40% | Technologies overlap with profile |
| Experience | 20% | Difficulty vs experience level |
| Repo Quality | 15% | Stars, activity, contributors |
| Freshness | 10% | Issue age and repo activity |
| Time Match | 10% | Estimated time vs availability |
| Interest | 5% | Topic overlap with interests |

### ML Enhancement
- Trained on user's labeled issues (like/dislike)
- XGBoost classifier with 50+ features
- Adjusts base score +/- 15 points
- Requires 200+ labeled issues

## Tech Stack

### Backend
- Python 3.11
- FastAPI + Pydantic
- SQLAlchemy 2.0 (async support)
- Celery + Redis
- XGBoost, scikit-learn
- Sentence-BERT embeddings

### Frontend
- React 19
- Vite (code splitting, HMR)
- React Query (TanStack)
- React Router
- Axios

### Infrastructure
- SQLite (dev) / PostgreSQL (prod)
- Redis (caching, task queue)
- Docker Compose

## Database Migrations

```bash
cd backend
alembic upgrade head          # Apply migrations
alembic revision -m "desc"    # Create migration
alembic downgrade -1          # Rollback one
```

## Testing

```bash
pytest tests/ -v
pytest tests/backend/ -v      # Backend only
pytest tests/ -k "test_name"  # Specific test
```

## Project Structure

```
contribution_matcher/
├── backend/
│   ├── app/
│   │   ├── routers/      # API endpoints
│   │   ├── services/     # Business logic
│   │   └── schemas.py    # Pydantic models
│   └── alembic/          # Database migrations
├── core/
│   ├── api/              # GitHub API client
│   ├── cache/            # Redis caching
│   ├── models/           # SQLAlchemy models
│   ├── repositories/     # Data access layer
│   ├── scoring/          # Scoring engine
│   └── services/         # Core services
├── frontend/
│   ├── src/
│   │   ├── api/          # API client
│   │   ├── components/   # React components
│   │   ├── context/      # Auth context
│   │   ├── hooks/        # Custom hooks
│   │   └── pages/        # Page components
│   └── vite.config.js
├── workers/
│   └── tasks/            # Celery tasks
└── tests/
```

## Performance Optimizations

### Frontend
- Lazy-loaded pages (React.lazy + Suspense)
- Component memoization (React.memo)
- Event handler optimization (useCallback)
- React Query caching (stale-while-revalidate)
- CSS containment and GPU acceleration
- Vendor chunk splitting

### Backend
- Connection pooling (QueuePool)
- Query optimization (selectinload, bulk updates)
- Response caching (Redis, 5-min TTL for stats)
- GZip compression (500+ byte responses)
- Batch bookmark lookups (2 queries vs N+1)

## Credits

Developed by Mohamed Ibrahim

