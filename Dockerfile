# syntax=docker/dockerfile:1

# Stage 1: Build stage with uv
FROM python:3.14-slim AS builder

# Install uv (Rust-based Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /cooking_recipe_api

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
# UV_COMPILE_BYTECODE: Compile Python files to bytecode for faster startup
# UV_LINK_MODE: Use copy mode for better compatibility in containers


# DEV args, default to false
ARG DEV=false

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$DEV" = "true" ]; then \
    uv sync --frozen --dev --no-install-project; \
    else \
    uv sync --frozen --no-install-project; \
    fi

# Stage 2: Runtime stage
FROM python:3.14-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r django-user && \
    useradd -r -g django-user -d /home/django-user -m django-user

# Set working directory
WORKDIR /cooking_recipe_api

# Copy uv binary from builder
COPY --from=builder /bin/uv /bin/uvx /bin/

# Copy virtual environment from builder
COPY --from=builder --chown=django-user:django-user /cooking_recipe_api/.venv /cooking_recipe_api/.venv

# Copy application code
COPY --chown=django-user:django-user . .

# Change to src directory where manage.py and Django app are located
WORKDIR /cooking_recipe_api/src

# Set environment variables
# PATH: Add venv binaries to PATH so Python/Django commands work directly
# PYTHONUNBUFFERED: Ensure Python output is sent straight to terminal without buffering
# PYTHONDONTWRITEBYTECODE: Prevent Python from writing .pyc files
# UV_PROJECT_ENVIRONMENT: Point uv to use the venv we created
ENV PATH="/cooking_recipe_api/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT="/cooking_recipe_api/.venv"

# Expose port 8000 for Django
EXPOSE 8000

# Switch to non-root user
USER django-user

# Health check (optional but recommended)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
#     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000').read()" || exit 1

# Default command (can be overridden)
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
