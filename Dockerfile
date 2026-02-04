# syntax=docker/dockerfile:1

# Stage 1: Build stage with uv
FROM python:3.14-alpine AS builder

# Install uv (Rust-based Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
# UV_COMPILE_BYTECODE: Compile Python files to bytecode for faster startup
# UV_LINK_MODE: Use copy mode for better compatibility in containers
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime stage
FROM python:3.14-alpine

# Install runtime dependencies
RUN apk add --no-cache \
    libpq \
    && rm -rf /var/cache/apk/*

# Create non-root user for security
RUN addgroup -S django-user && \
    adduser -S -G django-user -h /home/django-user django-user

# Set working directory
WORKDIR /app

# Copy uv binary from builder
COPY --from=builder /bin/uv /bin/uvx /bin/

# Copy virtual environment from builder
COPY --from=builder --chown=django-user:django-user /app/.venv /app/.venv

# Copy application code
COPY --chown=django-user:django-user . .

# Set environment variables
# PATH: Add venv binaries to PATH so Python/Django commands work directly
# PYTHONUNBUFFERED: Ensure Python output is sent straight to terminal without buffering
# PYTHONDONTWRITEBYTECODE: Prevent Python from writing .pyc files
# UV_PROJECT_ENVIRONMENT: Point uv to use the venv we created
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT="/app/.venv"

# Expose port 8000 for Django
EXPOSE 8000

# Switch to non-root user
USER django-user

# Health check (optional but recommended)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
#     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000').read()" || exit 1

# Default command (can be overridden)
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
