# Django Template

A batteries-included Django project template — production-ready from day one.

**Stack:**

| Layer | Technology |
|---|---|
| Web framework | Django 6 |
| ASGI server | Daphne |
| WebSockets | Django Channels |
| Background tasks | Celery + Redis |
| REST API | Django Ninja (OpenAPI / pydantic v2) |
| CSS | Tailwind CSS v4 |
| Hypermedia | htmx |
| Reactivity | Alpine.js |
| Static files | WhiteNoise |
| Auth | Custom `User(AbstractUser)` |
| Dev reloading | django-browser-reload |

---

## Requirements

- Python 3.11+
- Node.js 18+
- Redis (Celery broker; also used for production channel layer)

---

## Quick start

**With Docker (recommended):**

```bash
git clone <repo-url> my-project
cd my-project
cp .env.example .env   # set SECRET_KEY at minimum
make docker-build && make docker-up
```

**Without Docker (local `.venv`):**

```bash
git clone <repo-url> my-project
cd my-project
make setup       # creates .venv, installs deps, generates .env with SECRET_KEY, runs migrations, collects static
make run         # starts Daphne + Celery worker + Tailwind in parallel
```

Daphne binds to `0.0.0.0:8085` by default. Override with:

```bash
make dev HOST=127.0.0.1 PORT=8000
```

Run tests:

```bash
make test
```

See all available commands:

```bash
make help
```

---

## Makefile reference

| Command | Description |
|---|---|
| `make setup` | Full bootstrap: create `.venv`, install deps, generate `.env`, migrate, collectstatic |
| `make run` | Start Daphne + Celery worker + Tailwind in parallel |
| `make dev` | Start Daphne ASGI server only |
| `make worker` | Start Celery worker only |
| `make tailwind` | Watch and rebuild Tailwind CSS only |
| `make install` | Install Python + Node dependencies |
| `make env` | Create `.env` from `.env.example` with a generated `SECRET_KEY` (skips if `.env` exists) |
| `make migrate` | Apply database migrations |
| `make makemigrations` | Create new migrations |
| `make collectstatic` | Collect static files |
| `make check` | Run Django deployment checks (`manage.py check --deploy`) |
| `make startapp name=myapp` | Scaffold a new app in `apps/myapp/` with correct `AppConfig` naming |
| `make superuser` | Create a Django superuser |
| `make shell` | Open Django shell |
| `make test` | Run pytest with coverage report |
| `make docker-build` | Build Docker images |
| `make docker-up` | Start all services in the background |
| `make docker-up-dev` | Start all services + Tailwind watch (dev) |
| `make docker-down` | Stop and remove containers |
| `make docker-logs` | Tail logs for all services |
| `make docker-shell` | Open a shell in the web container |
| `make docker-manage cmd="..."` | Run a `manage.py` command inside the web container |
| `make lint` | Lint code with ruff |
| `make format` | Auto-format code with ruff |
| `make clean` | Remove `__pycache__`, `.pyc` files, and `db.sqlite3` |
| `make reset` | Full teardown and rebuild (`clean` + `setup`) |

---

## Manual setup

### 1. Clone the repository

```bash
git clone <repo-url> my-project
cd my-project
```

### 2. Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment variables

```bash
cp .env.example .env
# Edit .env — at minimum set a unique SECRET_KEY:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Key variables in `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | Active settings module |
| `SECRET_KEY` | *(required)* | Django secret key |
| `DEBUG` | `True` | Debug mode |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Database connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + prod channels |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Allowed hostnames |

### 5. Node dependencies

Copies Alpine.js and htmx to `static/js/` and builds Tailwind CSS automatically via `postinstall`.

```bash
npm install
```

### 6. Database migrations

```bash
python manage.py migrate
```

### 7. Superuser (optional)

```bash
python manage.py createsuperuser
```

---

## Docker

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine + Compose plugin.

The compose stack includes:

| Service | Image | Purpose |
|---|---|---|
| `web` | local build | Daphne ASGI server (runs migrate + collectstatic on start) |
| `worker` | local build | Celery worker |
| `redis` | `redis:7-alpine` | Celery broker + channel layer |
| `db` | `postgres:16-alpine` | PostgreSQL database |

Tailwind CSS is built into the image at build time (`npm install` → `postinstall`). For active CSS development, a `docker-compose.dev.yml` overlay adds a Tailwind watch container:

```bash
# First time
cp .env.example .env   # edit SECRET_KEY at minimum
make docker-build
make docker-up          # or: make docker-up-dev (includes Tailwind watch)

# Subsequent starts
make docker-up

# Start with Tailwind watch for active CSS dev
make docker-up-dev

# Tail logs
make docker-logs

# Run management commands
make docker-manage cmd="createsuperuser"
make docker-manage cmd="makemigrations"

# Open a shell
make docker-shell

# Stop everything
make docker-down
```

> The `web` container runs `migrate` and `collectstatic` automatically on startup.
> `DATABASE_URL` and `REDIS_URL` in `docker-compose.yml` override the values in your `.env` to point at the containerised services.

---

## Running the project (local, no Docker)

### Development server

```bash
make dev         # Daphne on 0.0.0.0:8085
make run         # Daphne + Celery + Tailwind in parallel
```

Visit [http://localhost:8085](http://localhost:8085).

### Celery worker

```bash
make worker
```

> Requires Redis on `localhost:6379`. Install: `brew install redis` / `sudo apt install redis-server`.

### Tailwind CSS (watch mode)

```bash
make tailwind
```

---

## Project structure

```
├── apps/                    # Project-specific Django apps (add yours here)
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings (environ, WhiteNoise, Channels, Celery)
│   │   ├── dev.py           # Dev overrides (browser-reload, plain static storage)
│   │   └── prod.py          # Prod overrides (Redis channels, security headers, SMTP)
│   ├── api.py               # Django Ninja API instance + endpoints
│   ├── asgi.py              # Channels ASGI router
│   ├── celery.py            # Celery app
│   ├── urls.py              # Root URL config
│   └── wsgi.py
├── core/                    # Main application
│   ├── migrations/
│   ├── templates/core/
│   │   └── index.html       # htmx + Alpine.js demo page
│   ├── admin.py             # UserAdmin
│   ├── consumers.py         # WebSocket consumer (Channels)
│   ├── models.py            # Custom User model
│   ├── routing.py           # WebSocket URL routes
│   ├── tasks.py             # Celery tasks
│   ├── tests.py             # pytest tests
│   ├── urls.py
│   └── views.py
├── templates/
│   └── base.html            # Base template (Tailwind, htmx, Alpine)
├── static/
│   ├── css/
│   │   ├── input.css        # Tailwind CSS entry point
│   │   └── output.css       # Built CSS (generated, gitignored)
│   └── js/
│       ├── alpine.min.js    # Copied from node_modules (gitignored)
│       └── htmx.min.js      # Copied from node_modules (gitignored)
├── .env                     # Local env vars (gitignored)
├── .env.example             # Env template (committed)
├── conftest.py              # pytest fixtures
├── Makefile                 # Common dev commands
├── package.json
├── pytest.ini
├── requirements.txt
└── tailwind.config.js
```

---

## Settings

Settings are split into three modules under `config/settings/`:

- **`base.py`** — shared across all environments
- **`dev.py`** — development only (browser-reload, plain static storage)
- **`prod.py`** — production (Redis channel layer, all security headers)

The active module is controlled by `DJANGO_SETTINGS_MODULE` in `.env`. Defaults to `config.settings.dev`.

To run in production mode locally:

```bash
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy
```

---

## API

Django Ninja exposes a REST API at `/api/`. Add endpoints in [config/api.py](config/api.py).

- **Swagger UI:** [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **Example:** `GET /api/hello` → `{"message": "Hello from Django Ninja!"}`

---

## WebSockets

A sample chat consumer is wired up at `ws/chat/<room_name>/`.

```javascript
const ws = new WebSocket("ws://127.0.0.1:8000/ws/chat/myroom/");
ws.onmessage = (e) => console.log(e.data);
ws.send(JSON.stringify({ message: "Hello!" }));
```

Add consumers in `core/consumers.py`, register routes in `core/routing.py`.

---

## Celery tasks

```python
# core/tasks.py
from celery import shared_task

@shared_task
def my_task(name):
    return f"Hello, {name}!"
```

```python
# from a view
from core.tasks import my_task
my_task.delay("World")
```

---

## Custom User model

`core.User` extends `AbstractUser`. Always use `AUTH_USER_MODEL` / `get_user_model()` for references:

```python
from django.contrib.auth import get_user_model
User = get_user_model()
```

---

## Static files

In development, Django serves static files directly. In production, WhiteNoise serves them via `CompressedManifestStaticFilesStorage`. Run `collectstatic` before deploying:

```bash
make collectstatic
# or
python manage.py collectstatic --no-input
```

---

## Testing

```bash
make test
```

Tests live in `core/tests.py`. Fixtures are in `conftest.py`. Settings default to `config.settings.dev` (see `pytest.ini`).

## Linting & formatting

```bash
make lint     # ruff check
make format   # ruff format
```

---

## Production checklist

- [ ] Set a strong `SECRET_KEY` in `.env`
- [ ] Set `DEBUG=False`
- [ ] Set `DJANGO_SETTINGS_MODULE=config.settings.prod`
- [ ] Set `DATABASE_URL` to a production database
- [ ] Set `REDIS_URL` to your Redis instance
- [ ] Set `ALLOWED_HOSTS` to your domain(s)
- [ ] Set `EMAIL_*` variables for transactional email
- [ ] Run `python manage.py collectstatic`
- [ ] Run `python manage.py check --deploy`
