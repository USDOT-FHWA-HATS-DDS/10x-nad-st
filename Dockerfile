# syntax=docker/dockerfile:1
# Stage 1: Build frontend assets
FROM node:current-slim AS frontend-builder
WORKDIR /app/nad_ch/controllers/web
COPY nad_ch/controllers/web/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install
COPY nad_ch/controllers/web ./
RUN npm run build

# Stage 2: Build Python dependencies
FROM python:3.13-slim AS python-builder
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install build tools and libraries for compilation with cache mounts
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    curl \
    binutils \
    build-essential \
    libgdal-dev \
    --no-install-recommends

# Install poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3 -
ENV PATH="${PATH}:/opt/poetry/bin"

WORKDIR /app
COPY pyproject.toml poetry.lock ./
# Refresh the lock file for Python 3.13 and updated dependencies
RUN poetry lock
RUN poetry self add poetry-plugin-export
RUN poetry export -f requirements.txt --output requirements.txt

# Install dependencies into a separate directory with pip cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --prefix=/install -r requirements.txt
# Add application code to builder for bytecode compilation
COPY nad_ch ./nad_ch
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini ./
RUN python -m compileall -x "node_modules|dist" .
RUN chmod +x scripts/*.sh

# Stage 3: Final Runtime Image
FROM python:3.13-slim
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install runtime GDAL libraries with cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    gdal-bin \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Add the current directory to the PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Create a non-root user to run the app
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

# Copy installed Python packages from the builder
COPY --from=python-builder /install /usr/local

# Copy pre-compiled application code from builder
COPY --from=python-builder --chown=appuser:appuser /app /app

# Copy built frontend assets
COPY --from=frontend-builder --chown=appuser:appuser /app/nad_ch/controllers/web/dist ./nad_ch/controllers/web/dist

USER appuser

# Start application
CMD ["/bin/sh", "./scripts/start_local.sh"]
