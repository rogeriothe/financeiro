FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

ENV UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=financeiro_project.settings \
    PORT=8000

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY . .

RUN uv sync

EXPOSE 8000

CMD ["uv", "run", "python", "src/manage.py", "runserver", "0.0.0.0:8000"]
