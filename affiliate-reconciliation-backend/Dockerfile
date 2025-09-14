# Multi-stage Dockerfile for Affiliate Reconciliation Platform
# Target: small runtime image, reproducible builds, production-ready defaults

# ===== Base builder image =====
FROM python:3.11-slim AS builder

ENV POETRY_VERSION=1.8.3 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (build-essential for any wheels requiring compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

ARG INSTALL_DEV=false

# Copy only dependency files first for better caching
COPY pyproject.toml poetry.lock* README.md ./

# Configure Poetry & refresh lock if pyproject changed (install only dependencies first)
RUN poetry config virtualenvs.create false \
  && poetry lock --no-update \
  && if [ "$INSTALL_DEV" = "true" ]; then \
       poetry install --no-interaction --no-ansi --no-root; \
     else \
       poetry install --no-interaction --no-ansi --no-root --without dev; \
     fi

# Copy application source (after deps layer so code changes don't invalidate dependency cache)
COPY . .

# Re-lock after copy (host poetry.lock may overwrite previous) then install project
RUN poetry lock --no-update \
  && if [ "$INSTALL_DEV" = "true" ]; then \
       poetry install --no-interaction --no-ansi; \
     else \
       poetry install --no-interaction --no-ansi --without dev; \
     fi

# ===== Runtime image =====
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    LOG_LEVEL=INFO \
    LOG_FILE=logs/app.log

WORKDIR ${APP_HOME}

# Create non-root user
RUN groupadd -r app && useradd -r -g app app

# Copy installed site-packages and application code from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Create logs directory & set permissions (whole app dir for test cache writes)
RUN mkdir -p logs && chown -R app:app /app

# Expose application port
EXPOSE 8000

USER app

# Default environment variables (override in compose or runtime)
ENV DATABASE_URL=sqlite:///./prod.db \
    QUEUE_SETTINGS_USE_REDIS=false

# Healthcheck (basic)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request, json; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Entrypoint uses uvicorn directly
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
