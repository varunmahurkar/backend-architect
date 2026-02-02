# Nurav AI - Backend Overview

> **For AI/LLM Models:** Read this file completely before making any changes. Update this file when project structure, dependencies, or features change.

---

## Project Summary

FastAPI backend for Nurav AI - provides LLM chat, web crawling, and authentication services. Supports multiple LLM providers (OpenAI, Anthropic, Google) via LangChain.

**Frontend:** `http://localhost:3000` (see `webportal/frontend-overview.md`)

---

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.113.0 | API framework |
| Pydantic | 2.8.0 | Data validation & settings |
| Uvicorn | Latest | ASGI server |
| LangChain | 0.3.13 | LLM orchestration |
| LangGraph | 0.2.59 | Agent workflows |
| Supabase | Latest | Database & auth verification |
| Crawlee | 0.3.0+ | Web crawling framework |
| Playwright | 1.40.0+ | Browser automation |
| BeautifulSoup4 | 4.12.0+ | HTML parsing |
| DuckDuckGo Search | 4.0.0+ | Web search |
| httpx | 0.25.0+ | Async HTTP client |
| PyJWT | 2.8.0+ | JWT token handling |

---

## Supported LLM Providers

| Provider | Default Model | Config Key |
|----------|---------------|------------|
| OpenAI | gpt-4o-mini | `OPENAI_API_KEY` |
| Anthropic | claude-3-5-sonnet-20241022 | `ANTHROPIC_API_KEY` |
| Google | gemini-2.0-flash | `GOOGLE_API_KEY` |

Default provider: `openai` (configurable via `DEFAULT_LLM_PROVIDER`)

---

## Folder Structure

```
backend-architect/
├── app/
│   ├── api/
│   │   ├── dependencies/       # Dependency injection
│   │   │   └── *.py            # Auth, DB dependencies
│   │   ├── models/             # Pydantic request/response models
│   │   │   └── *.py            # Data models
│   │   └── routes/             # API endpoint handlers
│   │       ├── __init__.py
│   │       ├── auth.py         # Authentication routes
│   │       ├── chat.py         # Chat/LLM routes
│   │       └── crawler.py      # Web crawler routes
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # App configuration (Pydantic Settings)
│   │
│   ├── prompts/                # LLM prompt templates
│   │   └── *.py                # System prompts, templates
│   │
│   └── services/               # Business logic layer
│       ├── __init__.py
│       ├── llm/                # LLM provider modules
│       │   └── *.py
│       ├── llm_service.py      # Multi-provider LLM service
│       ├── crawler_service.py  # Web crawling service
│       ├── bloom_filter_service.py  # URL deduplication
│       ├── password_service.py # Password hashing (bcrypt)
│       └── user_service.py     # User CRUD operations
│
├── main.py                     # FastAPI app entry point
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (DO NOT COMMIT)
├── .env.example                # Environment template
└── .venv/                      # Virtual environment
```

---

## API Endpoints

### Root
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API welcome message |
| GET | `/health` | Health check status |
| OPTIONS | `/*` | CORS preflight handler |

### Authentication (`/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login user |
| POST | `/auth/logout` | Logout user |
| GET | `/auth/me` | Get current user |
| POST | `/auth/refresh` | Refresh token |

### Chat (`/chat`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/` | Send message to LLM |
| POST | `/chat/stream` | Stream LLM response |

### Crawler (`/crawler`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/crawler/crawl` | Crawl single URL |
| POST | `/crawler/search` | Search and crawl results |

---

## Services

### LLM Service (`services/llm_service.py`)
Multi-provider LLM service supporting OpenAI, Anthropic, and Google.

```python
from app.services.llm_service import get_llm_response

response = await get_llm_response(
    messages=[{"role": "user", "content": "Hello"}],
    provider="openai"  # or "anthropic", "google"
)
```

### Crawler Service (`services/crawler_service.py`)
Web crawling with Playwright and BeautifulSoup.

```python
from app.services.crawler_service import crawl_url

content = await crawl_url("https://example.com")
```

### Bloom Filter Service (`services/bloom_filter_service.py`)
URL deduplication to avoid re-crawling.

### User Service (`services/user_service.py`)
User CRUD operations with Supabase.

### Password Service (`services/password_service.py`)
Secure password hashing with bcrypt.

---

## Configuration

Settings are managed via Pydantic Settings in `app/config/settings.py`.

```python
from app.config.settings import settings

# Access config
api_key = settings.openai_api_key
model = settings.openai_model

# Get provider-specific config
config = settings.get_llm_config("anthropic")
```

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `default_llm_provider` | openai | Default LLM to use |
| `rate_limit_per_minute` | 60 | API rate limit |
| `crawler_timeout` | 30 | Seconds per page |
| `crawler_max_content_length` | 50000 | Max chars per page |
| `crawler_max_concurrent` | 5 | Concurrent crawl jobs |
| `search_max_results` | 5 | Search results limit |

---

## Environment Variables

```env
# API
DEBUG=false
PORT=8000

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
DEFAULT_LLM_PROVIDER=openai

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...              # anon key
SUPABASE_SERVICE_ROLE_KEY=eyJ... # service role key
JWT_SECRET=your-jwt-secret

# Frontend
FRONTEND_URL=http://localhost:3000
AUTH_CALLBACK_URL=http://localhost:3000/auth/callback
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Crawler
CRAWLER_TIMEOUT=30
CRAWLER_USER_AGENT=NuravBot/1.0
```

---

## Running the Server

### Development
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Unix/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for crawling)
playwright install chromium

# Run server
python main.py
# or
uvicorn main:app --reload --port 8000
```

### Production
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Guidelines for AI Models

### Before Making Changes
1. Read this file completely
2. Check `app/config/settings.py` for existing config options
3. Check existing services in `app/services/`
4. Check existing routes in `app/api/routes/`

### Code Structure
- Routes go in `app/api/routes/`
- Business logic goes in `app/services/`
- Pydantic models go in `app/api/models/`
- Config options go in `app/config/settings.py`
- Dependencies go in `app/api/dependencies/`

### When Adding Features
1. Create Pydantic models for request/response
2. Add service logic in `services/`
3. Create route handler in `routes/`
4. Register router in `main.py`
5. Update settings if new config needed
6. Add to requirements.txt if new dependency

### Coding Standards
- Use async/await for I/O operations
- Use Pydantic models for all data validation
- Use dependency injection for auth, db access
- Handle errors with proper HTTP status codes
- Add docstrings to functions
- Use type hints throughout

### Files to Update After Changes
- [ ] `backend-overview.md` - This file (structure/features)
- [ ] `requirements.txt` - New dependencies
- [ ] `app/config/settings.py` - New config options
- [ ] `.env.example` - New environment variables
- [ ] `main.py` - Register new routers

---

## Recent Changes Log

> Update this section when making significant changes

| Date | Change | Files Affected |
|------|--------|----------------|
| 2026-02-01 | Created backend-overview.md | backend-overview.md |

---

## CORS Configuration

Allowed origins (configured in `main.py`):
- `http://localhost:3000`
- `http://127.0.0.1:3000`
- `http://localhost:3001`
- Value from `FRONTEND_URL` env
- Additional from `ALLOWED_ORIGINS` env (comma-separated)

---

## Database

Using Supabase for:
- User authentication verification
- User profile storage
- Session management

Key tables:
- `auth_users_table` - User profiles

Access via `SUPABASE_SERVICE_ROLE_KEY` to bypass RLS.

---

## Dependencies Quick Add

```bash
# Add new package
pip install <package>

# Update requirements.txt
pip freeze > requirements.txt
# OR manually add specific version
echo "<package>==<version>" >> requirements.txt
```

---

**Last Updated:** 2026-02-01
