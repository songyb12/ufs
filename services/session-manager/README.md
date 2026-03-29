# Session Manager

FastAPI service that manages Claude CLI sessions, pipelines, and shell terminals over a WebSocket/REST interface.

---

## Architecture

The service is split into focused modules after Phase 2 monolith decomposition:

| Module | Responsibility |
|--------|---------------|
| `app/main.py` | App factory, lifespan, middleware, static mounts, `/`, `/health`, WebSocket routes |
| `app/models.py` | Path constants, env-driven config constants, Pydantic request/response models |
| `app/state.py` | Shared mutable state (`sessions`, `pipelines`, `shell_sessions`, `plan_phases`, `CLAUDE_EXE`) |
| `app/auth.py` | Admin API key verification, browse-root allow-list |
| `app/session.py` | `ClaudeSession` — Claude CLI process lifecycle, prompt queue, streaming output |
| `app/shell.py` | `ShellSession` — ConPTY terminal via pywinpty (cmd / PowerShell) |
| `app/screen.py` | `ScreenMonitor` — periodic Windows screen capture (mss + Pillow) |
| `app/pipeline.py` | `PipelineRunner` + `PlanPhase` — supervisor-driven multi-step pipeline engine |
| `app/pipeline_store.py` | SQLite checkpoint store for pipeline run state and recovery |
| `app/routes_admin.py` | `/admin/*` endpoints (status, restart, resume) — requires `X-Admin-Key` |
| `app/routes_api.py` | All `/api/*` REST endpoints (sessions, pipelines, git, shell, templates, etc.) |

---

## Requirements

- Python 3.13+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) installed and accessible on `PATH`
- Windows (for `ShellSession` / `ScreenMonitor`; other features work cross-platform)
- Optional: `pywinpty` for ConPTY shell support, `mss`+`Pillow` for screen capture

---

## Installation & Running

### Local (pip)

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload
```

### Docker

```bash
docker build -t session-manager .
docker run -p 8006:8006 \
  -v $(pwd)/data:/app/data \
  -e ADMIN_API_KEY=your-secret-key \
  # -e TASK_TIMEOUT_DEFAULT=300 \
  # -e TASK_TIMEOUT_LONG=900 \
  # -e TASK_TIMEOUT_IMAGE_GEN=1800 \
  # -e MEDIA_TOKEN_TTL=3600 \
  session-manager
```

The `data/` volume persists sessions, logs, pipeline checkpoints, projects, and templates.

---

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ADMIN_API_KEY` | Secret key for `/admin/*` endpoints (`X-Admin-Key` header) | `""` (admin API disabled) | Recommended |
| `SERVICE_PORT` | HTTP listen port (when started via `__main__`) | `8006` | No |
| `LOG_LEVEL` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` | No |
| `ANTHROPIC_API_KEY` | Anthropic API key for pipeline `mode=api` supervisor calls | — | For API mode pipelines |
| `LLM_API_KEY` | Alias for `ANTHROPIC_API_KEY` (checked as fallback) | — | For API mode pipelines |
| `MAX_SESSIONS_PER_CLIENT` | Maximum concurrent active sessions per client IP | `10` | No |
| `ALLOW_GIT_WRITE` | Allow write git subcommands (`push`, `commit`, etc.) via `/api/git/exec` | `true` | No |
| `TASK_TIMEOUT_DEFAULT` | Idle timeout (seconds) for `task_type=default` send commands | `300` | No |
| `TASK_TIMEOUT_LONG` | Idle timeout (seconds) for `task_type=long_task` send commands | `900` | No |
| `TASK_TIMEOUT_IMAGE_GEN` | Idle timeout (seconds) for `task_type=image_gen` send commands | `1800` | No |
| `MEDIA_TOKEN_TTL` | Signed media token lifetime (seconds) for `/uploads` and `/screenshots` | `3600` | No |

> **Internal / not user-configurable**: `CLAUDECODE` (stripped from subprocess env to prevent nested sessions), `COMSPEC` (used to locate `cmd.exe`), `APPDATA` / `LOCALAPPDATA` (Claude CLI discovery on Windows).

---

## Task Timeout Configuration

Send commands accept a `task_type` parameter that selects the idle timeout for that operation:

| `task_type` | Env Variable | Default | Use Case |
|-------------|--------------|---------|----------|
| `default` | `TASK_TIMEOUT_DEFAULT` | 300s (5 min) | Normal prompts |
| `long_task` | `TASK_TIMEOUT_LONG` | 900s (15 min) | Long-running analysis |
| `image_gen` | `TASK_TIMEOUT_IMAGE_GEN` | 1800s (30 min) | Image generation |

The CLI process is killed and an error message is appended if no output is received within the timeout. A heartbeat system message is updated every 60 seconds to indicate progress.

**API usage:**

```http
POST /api/sessions/{id}/send
Content-Type: application/json

{"command": "Generate 10 images", "task_type": "image_gen"}
```

Response includes `idle_timeout` confirming which value was applied.

---

## Media Security

When `ADMIN_API_KEY` is set, `/uploads` and `/screenshots` are **not** served as public `StaticFiles`. Instead, access requires a time-limited signed token obtained from `/api/media-token`.

**Flow:**

1. Client calls `GET /api/media-token` → receives `{"token": "<sig>:<expires>", "expires": <unix_ts>, "auth_required": true}`
2. Token is refreshed automatically 10 minutes before expiry (default TTL: 1 hour)
3. Media URLs are rewritten: `/uploads/foo.png` → `/api/media/uploads/foo.png?mkey=<token>`

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/media-token` | Get HMAC-SHA256 signed token (empty token when auth disabled) |
| GET | `/api/media/{path}` | Serve upload or screenshot with optional `?mkey=` token |

Authentication failures (`401`/`403`) are logged at WARNING level with client IP and path. Path traversal attempts (`../../`) are blocked both by Starlette URL normalization and by `Path.is_relative_to()` filesystem validation.

When `ADMIN_API_KEY` is **not** set (development mode), `/uploads` and `/screenshots` are served directly as public `StaticFiles` with no token required.

---

## Running Tests

```bash
# Install dev dependencies (includes pytest, httpx)
pip install -r requirements-dev.txt

# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=app --cov-report=term-missing
```

Tests are split into:
- `tests/test_core.py` — unit tests for session, pipeline, and shell classes
- `tests/test_integration.py` — FastAPI route integration tests (httpx AsyncClient, no live CLI)

---

## API Endpoints Summary

### Core

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/` | Web UI (HTML) | — |
| GET | `/health` | Health check (`status`, `sessions`, `claude_cli`, `db_ok`) | — |
| GET | `/api/stats` | Session / pipeline / shell counts | — |

### Sessions

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/sessions` | List all sessions | — |
| GET | `/api/sessions/pending-restore` | Sessions with preview info (for restore UI) | — |
| POST | `/api/sessions` | Create session | — |
| POST | `/api/sessions/dismiss` | Bulk delete sessions | — |
| DELETE | `/api/sessions/{id}` | Kill session (`?remove=true` deletes state file) | — |
| POST | `/api/sessions/{id}/send` | Send prompt | — |
| POST | `/api/sessions/{id}/interrupt` | Interrupt running prompt (SIGINT) | — |
| GET | `/api/sessions/{id}/output` | Get output lines (`?lines=200`) | — |
| PATCH | `/api/sessions/{id}/rename` | Rename session | — |
| PATCH | `/api/sessions/{id}/model` | Change model | — |
| GET | `/api/sessions/{id}/export` | Export full conversation | — |
| POST | `/api/sessions/{id}/fork` | Fork session (copy conversation) | — |
| POST | `/api/sessions/{id}/upload` | Upload file to session work_dir | — |
| GET | `/api/sessions/{id}/claude-md` | Read CLAUDE.md | — |
| PUT | `/api/sessions/{id}/claude-md` | Write CLAUDE.md | — |
| WS | `/ws/{id}` | Real-time output stream (WebSocket) | — |

### Pipelines

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/pipelines` | Start pipeline (`session_id`, `goal`, `mode`, `supervisor_model`) | — |
| GET | `/api/pipelines` | List pipelines | — |
| GET | `/api/pipelines/{id}` | Pipeline status + history | — |
| POST | `/api/pipelines/{id}/stop` | Stop pipeline | — |
| DELETE | `/api/pipelines/{id}` | Remove from memory | — |
| POST | `/api/pipelines/cleanup` | Remove completed/failed pipelines | — |

### Plan Phases

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/plan-phases` | Start plan phase (generates clarifying questions) | — |
| GET | `/api/plan-phases` | List plan phases | — |
| GET | `/api/plan-phases/{id}` | Phase status + questions + plan | — |
| POST | `/api/plan-phases/{id}/answers` | Submit answers → generate plan | — |
| POST | `/api/plan-phases/{id}/approve` | Approve plan → launch pipeline | — |
| POST | `/api/plan-phases/{id}/regenerate` | Regenerate plan | — |
| DELETE | `/api/plan-phases/{id}` | Delete plan phase | — |

### Git

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/git/status` | `git status` | — |
| GET | `/api/git/log` | `git log` | — |
| GET | `/api/git/branches` | Branch list | — |
| GET | `/api/git/diff` | Diff (`?cached=true` for staged) | — |
| POST | `/api/git/exec` | Execute git subcommand (write ops require `ALLOW_GIT_WRITE=true`) | — |
| POST | `/api/git/clone` | Clone repository | — |
| GET | `/api/git/prs` | GitHub PR list (`gh pr list`) | — |
| GET | `/api/git/issues` | GitHub issue list | — |
| GET | `/api/git/remote` | Remote info | — |
| GET | `/api/git/gh-auth` | GitHub CLI auth status | — |
| GET | `/api/git/gh-repos` | Search GitHub repos | — |

### Shell Terminals

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/shells` | Create shell (cmd / powershell) — requires pywinpty | — |
| GET | `/api/shells` | List shells | — |
| DELETE | `/api/shells/{id}` | Kill shell | — |
| WS | `/ws/shell/{id}` | Shell I/O stream (xterm.js bridge) | — |

### Templates & Misc

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/templates` | List prompt templates | — |
| POST | `/api/templates` | Create template | — |
| DELETE | `/api/templates/{id}` | Delete template | — |
| GET | `/api/browse` | Browse directory | — |
| GET/POST/DELETE | `/api/projects` | Manage bookmarked projects | — |
| POST | `/api/compare` | Multi-model comparison | — |
| GET | `/api/logs` | List log files | — |
| GET | `/api/logs/{filename}` | Read log file | — |
| GET | `/api/media-token` | Get signed media token (empty when auth disabled) | — |
| GET | `/api/media/{path}` | Serve upload or screenshot with token auth (`?mkey=`) | — |

### Screen Monitor

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/monitor/start` | Start periodic capture (`?interval=30`) | — |
| POST | `/api/monitor/stop` | Stop monitoring | — |
| GET | `/api/monitor/capture` | Capture now | — |
| GET | `/api/monitor/latest` | Latest captured image | — |

### Admin (`X-Admin-Key` header required)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/admin/status` | Active pipelines + resumable runs + safe-to-restart flag | ✓ |
| POST | `/admin/restart` | Drain pipelines then `os.execv` restart | ✓ |
| POST | `/admin/resume/{run_id}` | Checkpoint info + resume hint for interrupted run | ✓ |

---

## Data Directory Layout

```
data/
  sessions/             # Session state JSON files ({session_id}.json)
  logs/                 # Per-session conversation logs ({name}_{timestamp}.log)
  uploads/              # Files uploaded via /api/sessions/{id}/upload
  screenshots/          # Screen captures from ScreenMonitor
  pipeline_state.db     # SQLite — pipeline run checkpoints
  projects.json         # Bookmarked project paths
  templates.json        # Saved prompt templates
```

All of `data/` should be mounted as a Docker volume to persist state across container restarts.
