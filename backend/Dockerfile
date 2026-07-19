# Multi-stage so the runtime image carries only the interpreter, the installed
# packages, and the application — no pip cache, no build tooling, no source
# wheels. Smaller image, smaller attack surface.

FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Dependencies are installed into a self-contained venv that the runtime stage
# copies wholesale. Copying requirements.txt alone first keeps this layer cached
# until the dependencies themselves change, rather than on every source edit.
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.14-slim AS runtime

# PYTHONUNBUFFERED so logs reach docker logs immediately rather than sitting in
# a buffer when the container is killed. PYTHONDONTWRITEBYTECODE because .pyc
# files in a read-heavy container are pure noise.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root: a container process that does not need to write to the filesystem
# should not be able to. Fixed UID so bind-mounted files have predictable
# ownership across machines.
RUN groupadd --gid 1001 app \
    && useradd --uid 1001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .

# Normalise line endings and set the executable bit here rather than relying on
# git: the entrypoint is authored on Windows, and a CRLF shebang makes the
# kernel fail with a bare "no such file or directory" that says nothing useful.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh

USER app

EXPOSE 8000

# Uses the stdlib rather than curl so the runtime image needs no extra packages.
# Compose gates nothing on the backend today, but the frontend will, and an
# unhealthy container should be visible in `docker compose ps` regardless.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else sys.exit(1)"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
