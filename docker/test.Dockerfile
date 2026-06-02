ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/code-agnostic-venv
WORKDIR /src

COPY pyproject.toml uv.lock ./
COPY code_agnostic/ code_agnostic/
COPY tests/ tests/

RUN uv sync --frozen --extra dev

ENTRYPOINT ["uv", "run", "--no-sync", "pytest"]
