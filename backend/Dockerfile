FROM python:3.12-alpine3.23@sha256:601d3d3797e90e2534782e69c85fafb7971b43f24c7b1b079b7e48dd435e458d AS builder

ENV PIP_NO_CACHE_DIR=1 PATH=/opt/venv/bin:$PATH
WORKDIR /build

RUN apk add --no-cache build-base cargo
COPY requirements.lock requirements-build.lock requirements-playwright-alpine.lock ./
RUN python -m venv /opt/venv \
    && pip install --require-hashes -r requirements-build.lock \
    && pip install --no-build-isolation --require-hashes -r requirements.lock \
    && pip install --no-deps --require-hashes \
        --target /opt/venv/lib/python3.12/site-packages \
        --platform manylinux1_x86_64 --implementation cp --python-version 3.12 \
        --only-binary=:all: -r requirements-playwright-alpine.lock \
    && pip uninstall -y maturin \
    && pip check

FROM python:3.12-alpine3.23@sha256:601d3d3797e90e2534782e69c85fafb7971b43f24c7b1b079b7e48dd435e458d AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_NODEJS_PATH=/usr/bin/node \
    PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium-browser \
    FORWARDED_ALLOW_IPS=127.0.0.1 \
    PATH=/opt/venv/bin:$PATH
WORKDIR /app

RUN apk add --no-cache chromium nodejs nss freetype harfbuzz ca-certificates font-freefont \
    && addgroup -g 10001 app \
    && adduser -D -u 10001 -G app -s /sbin/nologin app
COPY --from=builder /opt/venv /opt/venv

COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app kb ./kb

USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).read()"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
