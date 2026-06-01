FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock* ./
RUN uv sync --python 3.12 --group dev || uv sync --python 3.12 --group dev

COPY . .

EXPOSE 8000
