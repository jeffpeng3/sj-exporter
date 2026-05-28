FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

ENV UV_PYTHON_DOWNLOADS=0

RUN python3 -V

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY uv.lock pyproject.toml /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.13-slim

COPY --from=builder --chown=nonroot:nonroot /app /app

COPY --chown=nonroot:nonroot . /app

ENV PATH="/app/.venv/bin:$PATH"

ENV PYTHONUNBUFFERED=1

WORKDIR /app

CMD ["python3", "-u", "main.py"]