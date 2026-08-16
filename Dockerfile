# PeerLens — single container, single port, single data location.
#
#   docker run -p 8000:8000 -v peerlens-data:/app/data ghcr.io/cedricmaron/peerlens:latest

# ---------------------------------------------------------------------------
# Stage 1 — build the React application
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — install Python dependencies into a virtual environment
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS backend

WORKDIR /build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./backend/
RUN pip install --no-deps ./backend

# ---------------------------------------------------------------------------
# Stage 3 — runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="PeerLens" \
      org.opencontainers.image.description="AI-assisted scientific research quality control." \
      org.opencontainers.image.source="https://github.com/CedricMaron/peerlens" \
      org.opencontainers.image.licenses="MIT"

# Non-root: research data is the user's, and the container should not run as root.
RUN useradd --create-home --uid 1000 peerlens

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PEERLENS_DATA_DIR=/app/data \
    PEERLENS_PROMPTS_DIR=/app/prompts \
    PEERLENS_STATIC_DIR=/app/static

COPY --from=backend /opt/venv /opt/venv
COPY --from=frontend /build/dist /app/static
# Prompts are read at runtime so they can be inspected, diffed and improved.
COPY prompts /app/prompts

# The volume mount point. Owned by the app user so a fresh volume is writable.
RUN mkdir -p /app/data/uploads && chown -R peerlens:peerlens /app/data

USER peerlens
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "peerlens.main:app", "--host", "0.0.0.0", "--port", "8000"]
