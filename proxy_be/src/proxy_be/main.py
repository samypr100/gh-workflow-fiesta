"""FastAPI application wiring.

Routes translate between HTTP and the service. Policy lives in the service.
"""

import datetime
import http
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from proxy_be.admission import AdmissionVerdict
from proxy_be.github import GitHubClient
from proxy_be.logging import configure_logging
from proxy_be.schemas import (
    CatalogResponse,
    CreateRunRequest,
    CreateRunResponse,
    InterpretersResponse,
    RunnersResponse,
    RunStatusResponse,
)
from proxy_be.service import BenchmarkService, SubmissionRejected
from proxy_be.settings import Settings, get_settings

UNKNOWN_CLIENT = "unknown"

log = structlog.get_logger(__name__)


def _client_ip(request: Request) -> str:
    """Determine the address a request came from.

    Cloudflare sets `cf-connecting-ip` and it cannot be spoofed by the client
    once the request has passed through the edge. `x-forwarded-for` is the
    fallback for local Docker testing.

    Args:
        request: Incoming request.

    Returns:
        The client address, or a placeholder when none can be determined.
    """
    connecting = request.headers.get("cf-connecting-ip")
    if connecting is not None:
        return connecting
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded is not None:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return UNKNOWN_CLIENT


def _rejection_response(error: SubmissionRejected) -> Response:
    """Translate a rejection into the right HTTP status.

    Args:
        error: The rejection.

    Returns:
        A JSON response carrying the explanation.
    """
    if error.verdict is AdmissionVerdict.DUPLICATE:
        status = http.HTTPStatus.CONFLICT
        headers: dict[str, str] = {}
    elif error.verdict is AdmissionVerdict.RATE_LIMITED:
        status = http.HTTPStatus.TOO_MANY_REQUESTS
        headers = {"retry-after": str(error.retry_after_seconds)}
    else:
        status = http.HTTPStatus.BAD_REQUEST
        headers = {}
    return Response(
        content=f'{{"detail": "{error}"}}',
        status_code=status,
        media_type="application/json",
        headers=headers,
    )


def create_app(service: BenchmarkService, *, settings: Settings | None = None) -> FastAPI:
    """Build the application around a service.

    Args:
        service: Submission service to serve.
        settings: Configuration, or None to load it.

    Returns:
        The configured application.
    """
    resolved = get_settings() if settings is None else settings

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Release the service's connections on shutdown.

        Yields:
            Control while the application runs.
        """
        yield
        await service.aclose()

    app = FastAPI(
        title="Python concurrency benchmark explorer",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Report liveness.

        Returns:
            A fixed acknowledgement.
        """
        return {"status": "ok"}

    @app.get("/api/catalog", response_model=CatalogResponse)
    async def catalog() -> CatalogResponse:
        """Return the selectable workloads and execution models.

        Returns:
            The catalog.
        """
        return service.catalog()

    @app.get("/api/interpreters", response_model=InterpretersResponse)
    async def interpreters() -> InterpretersResponse:
        """Return the selectable interpreters.

        Returns:
            The interpreter list.
        """
        return await service.interpreters()

    @app.get("/api/runners", response_model=RunnersResponse)
    async def runners() -> RunnersResponse:
        """Return the available runner images.

        Returns:
            The runner list.
        """
        return service.runners()

    @app.post(
        "/api/runs",
        response_model=CreateRunResponse,
        status_code=http.HTTPStatus.ACCEPTED,
    )
    async def create_run(body: CreateRunRequest, request: Request) -> Response:
        """Accept a submission and dispatch it.

        Args:
            body: The submission.
            request: Incoming request, used to derive the user key.

        Returns:
            The run token, or an explanation of the refusal.
        """
        try:
            created = await service.create_run(
                selections=body.selections,
                client_ip=_client_ip(request),
                now=datetime.datetime.now(tz=datetime.UTC),
            )
        except SubmissionRejected as error:
            return _rejection_response(error)
        return Response(
            content=created.model_dump_json(),
            status_code=http.HTTPStatus.ACCEPTED,
            media_type="application/json",
        )

    @app.get("/api/runs/{run_token}", response_model=RunStatusResponse)
    async def run_status(run_token: str) -> Response:
        """Report progress and results for a run.

        Args:
            run_token: Token issued when the run was created.

        Returns:
            The status, or an explanation of the refusal.
        """
        try:
            status = await service.run_status(
                run_token,
                now=int(datetime.datetime.now(tz=datetime.UTC).timestamp()),
            )
        except SubmissionRejected as error:
            return _rejection_response(error)
        return Response(
            content=status.model_dump_json(),
            status_code=http.HTTPStatus.OK,
            media_type="application/json",
        )

    return app


def build_default_app() -> FastAPI:
    """Build the application from ambient configuration.

    Returns:
        The configured application.
    """
    settings = get_settings()
    configure_logging(debug=settings.debug)
    github = GitHubClient(
        token=settings.github_token.get_secret_value(),
        owner=settings.github_owner,
        repo=settings.github_repo,
        ref=settings.github_ref,
    )
    return create_app(BenchmarkService(settings=settings, github=github), settings=settings)


app = build_default_app()


def run() -> None:
    """Serve the application with uvicorn."""
    uvicorn.run("proxy_be.main:app", host="0.0.0.0", port=8000)
