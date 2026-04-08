# MATCHA Backend

FastAPI backend for MATCHA — a collaboration platform connecting bloggers and businesses in Bali.

## Tech Stack

- **FastAPI** + Uvicorn
- **PostgreSQL 16** (async via SQLAlchemy + asyncpg)
- **Redis 7** (caching)
- **Docker Compose** for production
- **S3-compatible storage** for photos (local fallback)

## Quick Start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | sqlite | PostgreSQL connection |
| `REDIS_URL` | - | Redis connection |
| `SECRET_KEY` | random | JWT signing key |
| `ENVIRONMENT` | development | dev / production |
| `STORAGE_BACKEND` | local | `local` or `s3` |
| `S3_BUCKET` | - | S3 bucket name |
| `S3_REGION` | eu-central-1 | AWS region |
| `S3_ACCESS_KEY` | - | AWS access key |
| `S3_SECRET_KEY` | - | AWS secret key |
| `USE_DB_REPOS` | false | Use PostgreSQL instead of InMemory |

## API Endpoints

### Auth `/api/v1/auth`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register (blogger/business) |
| POST | `/auth/login` | Login, returns JWT |
| GET | `/auth/me` | Current user info |
| DELETE | `/auth/me` | Delete account + all data |
| POST | `/auth/upload-photo` | Upload photo (local/S3) |
| POST | `/auth/verify` | Verify user |
| POST | `/auth/device-token` | Register push token |

### Matches `/api/v1/matches`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/matches/feed` | Discovery feed (filtered, ranked) |
| GET | `/matches` | Active matches (excludes expired 48h) |
| POST | `/matches/swipe` | Swipe (left/right/super) |
| POST | `/matches/match-back` | Instant mutual match |

Filters: `?niche=Travel&district=Canggu&min_followers=5000&collab_type=barter`

### Offers `/api/v1/offers`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/offers` | List offers (filterable) |
| POST | `/offers` | Create offer (business, costs 1 credit) |
| POST | `/offers/{id}/close` | Close offer |
| POST | `/offers/{id}/respond` | Respond (blogger, 3/day limit) |
| POST | `/offers/{id}/accept-response` | Accept response |
| POST | `/offers/{id}/decline-response` | Decline response |

Types: `barter`, `paid`, `both`. Slots: `slots_total=0` = unlimited.

### Deals `/api/v1/deals`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/deals` | User's deals |
| POST | `/deals` | Create (Draft) |
| POST | `/deals/{id}/accept` | Draft -> Confirmed |
| POST | `/deals/{id}/decline` | -> Cancelled |
| POST | `/deals/{id}/check-in` | Both sides -> Visited |
| POST | `/deals/{id}/cancel` | Cancel (reason required) |
| POST | `/deals/{id}/review` | Leave review |
| POST | `/deals/{id}/content-proof` | Upload proof URL |
| POST | `/deals/{id}/repeat` | Repeat (Black tier) |
| POST | `/deals/{id}/no-show` | Report no-show |

```
DRAFT -> CONFIRMED -> VISITED -> REVIEWED
           |             |
        CANCELLED     NO_SHOW
```

### Chats `/api/v1/chats`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/chats` | All conversations |
| GET | `/chats/{id}` | Chat with messages |
| POST | `/chats/{id}/messages` | Send message |
| GET | `/chats/{id}/quick-replies` | Contextual reply suggestions |
| POST | `/chats/{id}/mute` | Mute |
| POST | `/chats/{id}/unmute` | Unmute |
| POST | `/chats/{id}/unmatch` | Unmatch |

### Activity `/api/v1/activity`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/activity/summary` | Likes, deals, applications |

### Profile `/api/v1/profiles`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/profiles/me` | My profile |
| PUT | `/profiles/me` | Update profile |
| GET | `/profiles/{user_id}` | Public profile |

### Admin `/api/v1/admin`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin` | Dashboard (HTML) |
| GET | `/admin/stats` | Platform stats |
| GET | `/admin/users` | User list |

## Architecture

```
app/
  core/       # Config, DI container, security, storage
  database/   # SQLAlchemy ORM, sessions, Alembic
  modules/
    auth/     # Register, login, JWT, delete account
    chats/    # Messages, quick replies
    deals/    # Deal lifecycle, reviews
    matches/  # Swipes, feed, 48h timer
    offers/   # Marketplace, slots, responses
    profile/  # User profiles, photos
    activity/ # Feed aggregation
    admin/    # Dashboard, moderation
```

## Testing

```bash
pytest tests/ -v
```

## Production

```bash
docker compose -f docker-compose.prod.yml up -d
```
