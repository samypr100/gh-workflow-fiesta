# Built from the repository root so the uv workspace resolves:
#   docker build -f proxy_be/Dockerfile -t proxy-be .
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# uv stays in the runtime image: /api/interpreters probes it for the
# interpreter list rather than maintaining one by hand.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_MANAGED_PYTHON=0

COPY pyproject.toml uv.lock ./
COPY contract/ ./contract/
COPY proxy_be/ ./proxy_be/

RUN uv sync --frozen --no-dev --package proxy-be

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["uv", "run", "--no-dev", "--package", "proxy-be", "proxy-be"]
