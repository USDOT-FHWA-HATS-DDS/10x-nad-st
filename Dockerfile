# syntax=docker/dockerfile:1

# Stage 1: Common Runtime Image
FROM python:3.13-slim AS python-base
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install runtime GDAL libraries
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y \
    gdal-bin \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Add the current directory to the PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Create a non-root user to run the app
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

# Stage 2: Build Python dependencies
FROM python:3.13-slim AS python-builder
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install build tools and libraries for compilation
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y \
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
# Refresh the lock file if needed (usually done outside Docker but kept for safety)
RUN poetry lock
RUN poetry self add poetry-plugin-export
RUN poetry export -f requirements.txt --output requirements.txt

# Install dependencies into a separate directory
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 3: Build frontend assets
FROM node:current-slim AS frontend-builder
WORKDIR /app/nad_ch/controllers/web
COPY nad_ch/controllers/web/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install
COPY nad_ch/controllers/web ./
RUN npm run build

# Stage 4: Development Target (Lightweight, used with volumes)
FROM python-base AS dev
# Copy installed Python packages from the builder
COPY --from=python-builder /install /usr/local
# Copy only the compiled frontend assets from the frontend-builder
# This ensures a working UI even if volumes are mounted over /app
COPY --from=frontend-builder --chown=appuser:appuser /app/nad_ch/controllers/web/dist /app/nad_ch/controllers/web/dist

USER appuser
# Start application (expects code to be mounted at /app)
CMD ["/bin/sh", "./scripts/start_local.sh"]

# Stage 5: Production Target (Self-contained, pre-compiled)
FROM dev AS production
USER root
# Add the rest of the application code to production image
COPY . .
# Perform bytecode compilation
RUN python -m compileall -x "node_modules|dist" .
RUN chmod +x scripts/*.sh
# Re-copy dist to ensure it is correctly permissioned and updated in the final layer
COPY --from=frontend-builder --chown=appuser:appuser /app/nad_ch/controllers/web/dist ./nad_ch/controllers/web/dist
USER appuser
