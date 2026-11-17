# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.12.12 /uv /usr/local/bin/uv
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base AS runtime
RUN groupadd --system app && useradd --system --gid app --home /app app
COPY --from=deps /app/.venv /app/.venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
ENV PATH="/app/.venv/bin:$PATH" STORAGE_DIR=/data/objects
RUN mkdir -p /data/objects && chown -R app:app /data
USER app
EXPOSE 8101
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8101/healthz').status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8101", "--proxy-headers"]
