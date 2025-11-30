# Contribution Matcher

An intelligent system that discovers GitHub issues, matches them to your developer skills, and recommends contribution opportunities using hybrid scoring (rules + ML).

## Quick Start

```bash
# Clone and install
git clone <repo-url> && cd contribution_matcher
pip install -r requirements.txt

# Set up environment
cp docker/env.example .env
# Edit .env with your GitHub credentials

# Start backend
source venv/bin/activate
uvicorn backend.app.main:app --reload

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Visit http://localhost:5173

## Features

- **GitHub OAuth Login** - Sign in with your GitHub account
- **Issue Discovery** - Find issues labeled "good first issue", "help wanted", etc.
- **Smart Matching** - Score issues against your skills, experience, interests
- **ML-Enhanced Scoring** - Train personalized models on your preferences
- **Multiple Profiles** - Create from GitHub repos, resume PDF, or manually

## Architecture

```
contribution_matcher/
├── core/                    # Shared library
│   ├── cache/               # Redis caching
│   ├── database/            # SQLAlchemy + legacy SQLite
│   ├── models/              # ORM models
│   ├── repositories/        # Data access layer
│   ├── scoring/             # Issue scoring + ML
│   ├── security/            # Encryption + rate limiting
│   └── services/            # Business logic
├── backend/                 # FastAPI API
├── workers/                 # Celery background tasks
├── frontend/                # React SPA
└── docker/                  # Docker configuration
```

## Configuration

Required environment variables:

| Variable | Description |
|----------|-------------|
| `JWT_SECRET_KEY` | Min 32 chars for JWT signing |
| `GITHUB_CLIENT_ID` | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app secret |
| `PAT_TOKEN` | GitHub PAT for issue discovery |

Optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///contribution_matcher.db` | Database connection |
| `REDIS_HOST` | `localhost` | Redis for caching |
| `TOKEN_ENCRYPTION_KEY` | - | Fernet key for token encryption |

Generate keys:
```bash
# JWT secret
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## CLI Commands

```bash
# Discover issues
python main.py discover --limit 100

# List from database
python main.py list --difficulty beginner --limit 10

# View statistics
python main.py stats

# Score issues against profile
python main.py score --top 10

# Create profile
python main.py create-profile --github your-username
python main.py create-profile --resume path/to/resume.pdf

# Train ML model (after labeling 200+ issues)
python main.py train-model
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/github` | GET | GitHub OAuth |
| `/api/issues` | GET | List issues |
| `/api/issues/discover` | POST | Discover new |
| `/api/profile` | GET/PUT | Profile |
| `/api/ml/train` | POST | Train model |

## Docker Deployment

```bash
# Copy environment
cp docker/env.example .env
# Edit .env

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head
```

Services:
- `api` - FastAPI (port 8000)
- `worker-discovery` - Celery (GitHub API)
- `worker-scoring` - Celery (scoring)
- `worker-ml` - Celery (ML training)
- `scheduler` - Celery beat
- `postgres` - PostgreSQL 15
- `redis` - Redis 7

## Scoring Algorithm

**Rule-Based (100 points):**
- Skill match: 40%
- Experience match: 20%
- Repo quality: 15%
- Freshness: 10%
- Time match: 10%
- Interest match: 5%

**ML Adjustment:**
- Trained on your labeled issues (good/bad)
- Adjusts score ±15 points based on prediction confidence

## Testing

```bash
pytest tests/ -v -p no:asyncio
```

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Celery
- **Frontend:** React 19, Vite
- **Database:** SQLite (dev), PostgreSQL (prod)
- **Caching:** Redis
- **ML:** XGBoost, scikit-learn, Sentence-BERT

## Documentation

See `docs/PROJECT_STATE.md` for detailed architecture and `docs/TODO.md` for remaining work.

## Credits

Created by Mohamed Ibrahim.
