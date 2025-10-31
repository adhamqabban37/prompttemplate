# FastAPI Project - Development

## 🚀 Fast Dev on Windows (No Docker rebuilds)

**Problem:** Running `pip install -e .` hangs for hours, and Docker rebuilds are slow.

**Solution:** Run FastAPI directly on Windows with hot-reload. Use Docker only for Postgres/Redis.

### Why pip install was slow

Your backend has these heavy dependencies that compile C extensions on Windows:

- `sentence-transformers` → Downloads 400MB+ ML models + compiles PyTorch/NumPy
- `lxml` → Compiles XML parser from C source
- `bcrypt`, `psycopg[binary]` → Cryptography and database drivers with native code
- `crewai` + `litellm` → Large AI frameworks with many transitive deps

On Windows, pip builds these from source unless pre-built wheels exist for your Python version, which causes 30-60 min installs.

### ⚡ Quick Start (3 minutes)

**1. Rebuild venv cleanly:**

```powershell
cd c:\dev\projects-template\backend
.\rebuild_venv.ps1
```

This script:

- Kills stuck pip/python processes
- Deletes corrupted `.venv`
- Creates fresh venv
- Upgrades pip/setuptools/wheel
- Installs all deps (detects `uv` for 10x speedup)

**2. Start Docker infra only:**

```powershell
cd c:\dev\projects-template
docker compose up -d db redis adminer
```

**3. Run backend with hot-reload:**

```powershell
cd backend
.\run_backend.ps1
```

Backend runs at: http://localhost:8001/docs

**4. Run frontend (optional):**

```powershell
cd frontend
npm install  # first time only
npm run dev
```

Frontend runs at: http://localhost:5174

### Docker Compose Only for Infra

To avoid rebuilding Docker images, start only database services:

```powershell
# Start infra (no build)
docker compose up -d db redis adminer

# Stop backend/frontend containers if running
docker compose stop backend frontend worker
```

Your `.env` file will be read by the PowerShell scripts for API keys (Stripe, PSI, etc).

### Performance Tips

- **Install `uv`** for 10-100x faster Python installs:

  ```powershell
  pip install uv
  ```

  Then use `uv sync` instead of `pip install -e .`

- **Use binary packages** (already configured):

  - ✅ `psycopg[binary]` instead of `psycopg` (no PostgreSQL build tools needed)
  - ✅ `bcrypt==4.3.0` pinned (avoids Rust compiler)

- **Skip heavy deps in dev** (optional):
  Comment out in `pyproject.toml` if not needed:

  - `crewai`, `litellm` (AI features)
  - `sentence-transformers`, `keybert` (ML keyphrase extraction)

- **Pre-download models** (one-time):
  The first run downloads ML models (~500MB) for `sentence-transformers`. This only happens once per venv.

---

## Docker Compose

- Start the local stack with Docker Compose:

```bash
docker compose watch
```

- Now you can open your browser and interact with these URLs:

Frontend, built with Docker, with routes handled based on the path: http://localhost:5173

Backend, JSON based web API based on OpenAPI: http://localhost:8000

Automatic interactive documentation with Swagger UI (from the OpenAPI backend): http://localhost:8000/docs

Adminer, database web administration: http://localhost:8080

Traefik UI, to see how the routes are being handled by the proxy: http://localhost:8090

**Note**: The first time you start your stack, it might take a minute for it to be ready. While the backend waits for the database to be ready and configures everything. You can check the logs to monitor it.

To check the logs, run (in another terminal):

```bash
docker compose logs
```

To check the logs of a specific service, add the name of the service, e.g.:

```bash
docker compose logs backend
```

## Local Development

The Docker Compose files are configured so that each of the services is available in a different port in `localhost`.

For the backend and frontend, they use the same port that would be used by their local development server, so, the backend is at `http://localhost:8000` and the frontend at `http://localhost:5173`.

This way, you could turn off a Docker Compose service and start its local development service, and everything would keep working, because it all uses the same ports.

For example, you can stop that `frontend` service in the Docker Compose, in another terminal, run:

```bash
docker compose stop frontend
```

And then start the local frontend development server:

```bash
cd frontend
npm run dev
```

Or you could stop the `backend` Docker Compose service:

```bash
docker compose stop backend
```

And then you can run the local development server for the backend:

````bash
cd backend
fastapi dev app/main.py

## Fast dev without Docker rebuilds (recommended)

To avoid image rebuilds on every code change, run the app services on your host with hot-reload and keep only infra in Docker:

- Docker: db, redis, proxy, adminer
- Host: backend (uvicorn --reload), worker (python -m app.worker), frontend (Vite dev server)

One-command setup on Windows (PowerShell):

1) Start from repo root and run the helper script:

```powershell
pwsh -NoLogo -NoProfile -File .\scripts\dev-host.ps1
````

What it does:

- Starts Docker infra with `docker compose up -d db redis proxy adminer` (no build)
- Creates a Python venv under `backend/.venv` if missing and installs deps
- Exports sensible dev env vars (DB/Redis, CORS, metrics)
- Opens separate terminals for:
  - Backend at http://localhost:8001 (uvicorn --reload)
  - Worker consuming background jobs
  - Frontend at http://localhost:5174 (Vite dev server)

Notes:

- Edit `.env` in the repo root to add API keys (e.g., `PSI_API_KEY`, `STRIPE_SECRET_KEY`) if you want those features during dev.
- Use `docker compose up -d` (without `--build`) to restart infra fast. Only rebuild images when you change dependencies or Dockerfiles.
- The frontend already proxies `/api` to the backend in dev, so calls like `fetch('/api/...')` work without extra config.

````

## Docker Compose in `localhost.tiangolo.com`

When you start the Docker Compose stack, it uses `localhost` by default, with different ports for each service (backend, frontend, adminer, etc).

When you deploy it to production (or staging), it will deploy each service in a different subdomain, like `api.example.com` for the backend and `dashboard.example.com` for the frontend.

In the guide about [deployment](deployment.md) you can read about Traefik, the configured proxy. That's the component in charge of transmitting traffic to each service based on the subdomain.

If you want to test that it's all working locally, you can edit the local `.env` file, and change:

```dotenv
DOMAIN=localhost.tiangolo.com
````

That will be used by the Docker Compose files to configure the base domain for the services.

Traefik will use this to transmit traffic at `api.localhost.tiangolo.com` to the backend, and traffic at `dashboard.localhost.tiangolo.com` to the frontend.

The domain `localhost.tiangolo.com` is a special domain that is configured (with all its subdomains) to point to `127.0.0.1`. This way you can use that for your local development.

After you update it, run again:

```bash
docker compose watch
```

When deploying, for example in production, the main Traefik is configured outside of the Docker Compose files. For local development, there's an included Traefik in `docker-compose.override.yml`, just to let you test that the domains work as expected, for example with `api.localhost.tiangolo.com` and `dashboard.localhost.tiangolo.com`.

## Docker Compose files and env vars

There is a main `docker-compose.yml` file with all the configurations that apply to the whole stack, it is used automatically by `docker compose`.

And there's also a `docker-compose.override.yml` with overrides for development, for example to mount the source code as a volume. It is used automatically by `docker compose` to apply overrides on top of `docker-compose.yml`.

These Docker Compose files use the `.env` file containing configurations to be injected as environment variables in the containers.

They also use some additional configurations taken from environment variables set in the scripts before calling the `docker compose` command.

After changing variables, make sure you restart the stack:

```bash
docker compose watch
```

## The .env file

The `.env` file is the one that contains all your configurations, generated keys and passwords, etc.

Depending on your workflow, you could want to exclude it from Git, for example if your project is public. In that case, you would have to make sure to set up a way for your CI tools to obtain it while building or deploying your project.

One way to do it could be to add each environment variable to your CI/CD system, and updating the `docker-compose.yml` file to read that specific env var instead of reading the `.env` file.

## Pre-commits and code linting

we are using a tool called [pre-commit](https://pre-commit.com/) for code linting and formatting.

When you install it, it runs right before making a commit in git. This way it ensures that the code is consistent and formatted even before it is committed.

You can find a file `.pre-commit-config.yaml` with configurations at the root of the project.

#### Install pre-commit to run automatically

`pre-commit` is already part of the dependencies of the project, but you could also install it globally if you prefer to, following [the official pre-commit docs](https://pre-commit.com/).

After having the `pre-commit` tool installed and available, you need to "install" it in the local repository, so that it runs automatically before each commit.

Using `uv`, you could do it with:

```bash
❯ uv run pre-commit install
pre-commit installed at .git/hooks/pre-commit
```

Now whenever you try to commit, e.g. with:

```bash
git commit
```

...pre-commit will run and check and format the code you are about to commit, and will ask you to add that code (stage it) with git again before committing.

Then you can `git add` the modified/fixed files again and now you can commit.

#### Running pre-commit hooks manually

you can also run `pre-commit` manually on all the files, you can do it using `uv` with:

```bash
❯ uv run pre-commit run --all-files
check for added large files..............................................Passed
check toml...............................................................Passed
check yaml...............................................................Passed
ruff.....................................................................Passed
ruff-format..............................................................Passed
eslint...................................................................Passed
prettier.................................................................Passed
```

## URLs

The production or staging URLs would use these same paths, but with your own domain.

### Development URLs

Development URLs, for local development.

Frontend: http://localhost:5173

Backend: http://localhost:8000

Automatic Interactive Docs (Swagger UI): http://localhost:8000/docs

Automatic Alternative Docs (ReDoc): http://localhost:8000/redoc

Adminer: http://localhost:8080

Traefik UI: http://localhost:8090

MailCatcher: http://localhost:1080

### Development URLs with `localhost.tiangolo.com` Configured

Development URLs, for local development.

Frontend: http://dashboard.localhost.tiangolo.com

Backend: http://api.localhost.tiangolo.com

Automatic Interactive Docs (Swagger UI): http://api.localhost.tiangolo.com/docs

Automatic Alternative Docs (ReDoc): http://api.localhost.tiangolo.com/redoc

Adminer: http://localhost.tiangolo.com:8080

Traefik UI: http://localhost.tiangolo.com:8090

MailCatcher: http://localhost.tiangolo.com:1080
