# Backend image for Cloudflare Containers.
#
# Built from the REPOSITORY ROOT, because this copies the whole uv workspace:
#   docker build -f proxy_be/Dockerfile -t proxy-be .
# wrangler.jsonc sets "image_build_context": "." so `wrangler deploy` does the
# same thing.
#
# No secrets are baked in. GITHUB_TOKEN, TOKEN_SECRET and USER_KEY_SECRET
# arrive at runtime as environment variables, set by the Worker from Cloudflare
# secrets. `pydantic-settings` reads them from the environment, so nothing in
# the image is Cloudflare-specific.

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dependency layer first: it changes far less often than the source, so edits
# to proxy_be/ do not invalidate the resolved environment.
COPY pyproject.toml uv.lock ./
# Every workspace member's manifest must be present or `uv sync --frozen`
# refuses to resolve, even for members it will not install. bench/ is declared
# in the root pyproject.toml, so its manifest comes along; its source does not.
COPY contract/pyproject.toml ./contract/
COPY proxy_be/pyproject.toml ./proxy_be/
COPY bench/pyproject.toml ./bench/
RUN uv sync --frozen --no-dev --no-install-workspace --package proxy-be

COPY contract/ ./contract/
COPY proxy_be/ ./proxy_be/
RUN uv sync --frozen --no-dev --package proxy-be


FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS runtime

WORKDIR /app

# uv stays in the runtime image on purpose: GET /api/interpreters shells out to
# `uv python list` rather than maintaining a hand-written catalogue of
# interpreter builds.
#
# UV_NO_MANAGED_PYTHON must remain unset or "0". When it is truthy,
# `uv python list --only-downloads` returns an empty array with exit status
# zero and no warning, and the interpreter dropdown is silently empty with
# nothing in the logs to explain why.
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_MANAGED_PYTHON=0 \
    UV_CACHE_DIR=/tmp/uv-cache

COPY --from=builder /app /app

# The backend holds no state and writes nothing it needs to keep, so it has no
# reason to run as root.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --no-create-home app \
    && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]

# Run the console script from the synced environment directly. Going through
# `uv run` would re-resolve the workspace on every container start.
CMD ["proxy-be"]
