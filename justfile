default:
    just --list

dev:
    uv run uvicorn apps.api.main:app --reload --port 8000

up:
    docker compose up -d

down:
    docker compose down

logs:
    docker compose logs -f

migrate:
    uv run alembic upgrade head

migration name:
    uv run alembic revision --autogenerate -m "{{name}}"

db-reset:
    docker compose down -v && docker compose up -d postgres && sleep 3 && just migrate

lint:
    uv run ruff check . && uv run ruff format .

typecheck:
    uv run mypy .

test:
    uv run pytest -v

crawl:
    uv run python -m workers.crawl_worker

playwright:
    uv run playwright install chromium
