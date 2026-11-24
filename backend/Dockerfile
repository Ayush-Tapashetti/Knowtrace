# KnowTrace API. Build context: ./backend
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    APP_ENV=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    DATABASE_URL=sqlite:////data/knowtrace.db \
    CURRICULUM_DIR=/app/content/seed

WORKDIR /app

# Pinned dependencies first so this layer is cached until the lock file changes.
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY src ./src
COPY content ./content

# Run as an unprivileged user; /data holds the SQLite file (mount a volume there).
RUN useradd --system --uid 10001 knowtrace && mkdir -p /data && chown knowtrace /data
USER knowtrace
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).status == 200 else 1)"

# --proxy-headers: behind nginx the real client IP comes from X-Forwarded-For, so the rate limiter
# counts each learner separately instead of counting the proxy.
CMD ["uvicorn", "knowtrace.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
