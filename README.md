# Contribution Matcher

Discovers GitHub issues and matches them to developer skills using hybrid scoring (rules + ML).

## Quick Start

```bash
git clone <repo-url> && cd contribution_matcher
pip install -r requirements.txt
cp docker/env.example .env  # Edit with GitHub credentials

# Backend
source venv/bin/activate
uvicorn backend.app.main:app --reload

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Visit http://localhost:5173

## Features

- GitHub OAuth login
- Issue discovery (good first issue, help wanted)
- Smart matching (skills, experience, interests)
- ML-enhanced scoring
- Multiple profile sources (GitHub, resume PDF, manual)

## Configuration

**Required:**
- `JWT_SECRET_KEY` (min 32 chars)
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`
- `PAT_TOKEN` (GitHub PAT)

**Optional:**
- `DATABASE_URL` (default: `sqlite:///contribution_matcher.db`)
- `REDIS_HOST` (default: `localhost`)
- `TOKEN_ENCRYPTION_KEY` (Fernet key)

**Generate keys:**
```bash
# JWT secret
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## CLI Commands

```bash
python main.py discover --limit 100
python main.py list --difficulty beginner --limit 10
python main.py stats
python main.py score --top 10
python main.py create-profile --github your-username
python main.py train-model  # After labeling 200+ issues
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/github` | GET | GitHub OAuth |
| `/api/issues` | GET | List issues |
| `/api/issues/discover` | POST | Discover new |
| `/api/profile` | GET/PUT | Profile |
| `/api/ml/train` | POST | Train model |

## Docker

```bash
cp docker/env.example .env  # Edit .env
docker-compose up -d
docker-compose exec api alembic upgrade head
```

**Services:** `api` (FastAPI), `worker-discovery/scoring/ml` (Celery), `scheduler` (Celery beat), `postgres`, `redis`

## Scoring

**Rule-based (100 points):** Skill match 40%, Experience 20%, Repo quality 15%, Freshness 10%, Time match 10%, Interest 5%

**ML adjustment:** ±15 points based on labeled issue preferences

## Tech Stack

Python 3.11, FastAPI, SQLAlchemy, Celery | React 19, Vite | SQLite/PostgreSQL | Redis | XGBoost, scikit-learn, Sentence-BERT

## Testing

```bash
pytest tests/ -v -p no:asyncio
```

## Documentation

See `docs/PROJECT_STATE.md` (architecture) and `docs/TODO.md` (remaining work).

## Development Notes

Proof of concept. Most development done locally with minimal commits to maintain GitHub Actions workflow stability. Current priorities: issue discovery pipeline, ML training data collection, frontend polish, Celery deployment, production infrastructure.

**Credits:** Mohamed Ibrahim
