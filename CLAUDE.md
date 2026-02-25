# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the server:**
```bash
uv run uvicorn app.main:app --reload --port 8000
```

**Install dependencies:**
```bash
uv sync
```

**Lint:**
```bash
uv run ruff check .
uv run ruff format .
```

**Environment variables required:**
- `DATABASE_URL` — PostgreSQL connection string (default: `postgresql://app_user:app_password@localhost:5432/knowledge_extraction`)
- `ANTHROPIC_API_KEY` — Required by the Claude Agent SDK for all AI queries
- `REPOS_ROOT_DIR` — Directory where cloned repos are stored (default: `.repos`)
- `SESSION_TIMEOUT_MINUTES` — Session expiry (default: 10080 = 7 days)
- `LOG_LEVEL` — Logging level (default: INFO)

**Docker:**
```bash
docker build -t knowledge-extraction-api .
docker run -p 8000:8000 -e DATABASE_URL=... -e ANTHROPIC_API_KEY=... knowledge-extraction-api
```

## Architecture

This is a FastAPI service that provides AI-powered codebase analysis. It manages "projects", each linked to a local or GitHub-cloned repository. The core feature is using the **Claude Agent SDK** to analyze codebases and answer questions via chat sessions or generate documentation.

### Key Data Flow

**Documentation generation** (`POST /projects/{id}/add-repo`):
1. Clones a GitHub repo to `.repos/{name}`
2. Spawns a background thread with a new event loop
3. Runs `query_codebase_markdown` / `query_codebase_json` (Claude Agent SDK) for each doc prompt in the registry
4. Stores results in the `pages` table (JSONB for structured, TEXT for markdown)

**Chat sessions** (`POST /sessions/{id}/chat`):
1. Loads session + message history from PostgreSQL
2. If first message + special session type → uses a predefined template (e.g., new feature analysis)
3. Otherwise → builds prompt from conversation history
4. Calls Claude Agent SDK with `Read`, `Glob`, `Grep` tools scoped to the project's `repo_path`
5. Persists updated message history back to DB

### Module Map

- `app/main.py` — FastAPI app, lifespan, CORS, router registration, yoyo migrations on startup
- `app/db.py` — PostgreSQL connection pool (psycopg2), MongoDB-style CRUD helpers. DB rows use `id`; API responses convert to `_id`. JSONB columns: `pages.content` and `sessions.message_history`
- `app/dependencies.py` — FastAPI dependency injection for `SessionManager` (singleton via `set_session_manager`) and `APISession` (loaded per-request)
- `app/services/agent.py` — Three agent functions:
  - `query_codebase()` — plain text response
  - `query_codebase_markdown()` — markdown text response
  - `query_codebase_json()` — structured output via `ResultMessage.structured_output` (see MEMORY.md)
- `app/services/sessions.py` — `SessionManager` (PostgreSQL-backed), `APISession` dataclass, history helpers
- `app/services/doc_prompts/` — Registry of prompt configs. Each entry has `name`, `prompt_template`, and `schema` (Pydantic model or `None` for markdown)
- `app/services/session_templates/` — Registry of first-message templates keyed by `SessionType`. Add new types by: (1) adding to `SessionType` enum, (2) creating a template function, (3) registering in `session_templates/__init__.py`
- `app/models/schemas.py` — All Pydantic request/response models
- `app/models/session_types.py` — `SessionType` enum (`GENERAL`, `NEW_FEATURE`)
- `migrations/` — yoyo migration SQL files applied automatically on startup

### Adding a New Doc Prompt

1. Create `app/services/doc_prompts/my_prompt.py` with a dict: `{"name": "...", "prompt_template": "...", "schema": MyPydanticModel | None}`
2. Register it in `app/services/doc_prompts/__init__.py`

### Adding a New Session Type

1. Add to `SessionType` enum in `app/models/session_types.py`
2. Create template in `app/services/session_templates/`
3. Register in `app/services/session_templates/__init__.py`
4. Add a DB migration if the new value isn't handled by the existing `session_type` column

### Database Conventions

- All primary keys are UUIDs
- `TABLE_COLUMNS` in `app/db.py` must be updated when adding columns — it controls which fields are inserted
- `content` on `pages` and `message_history` on `sessions` are JSONB and require `psycopg2.extras.Json()` wrapping (handled automatically in `add_item` / `update_item`)
- Migrations use yoyo-migrations; add new `.sql` files to `migrations/` with `-- migrate: apply` / `-- migrate: rollback` markers
