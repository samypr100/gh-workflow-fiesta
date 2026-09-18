"""Asynchronous client for the subset of the GitHub API this backend uses."""

import datetime
import enum
import http
import io
import re
import zipfile

import httpx
import structlog
from bench_contract.dispatch import (
    ARTIFACT_PREFIX,
    RESULT_FILENAME,
    WORKFLOW_FILENAME,
    DispatchInput,
    DispatchMatrix,
)
from bench_contract.results import RunResult
from pydantic import BaseModel, ConfigDict, ValidationError

API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"
REQUEST_TIMEOUT_S = 30.0
RUN_PAGE_SIZE = 50
RUN_NAME_PATTERN = re.compile(r"^bench (?P<submission>\S+) \[(?P<user_key>[a-z0-9]+)\]$")

log = structlog.get_logger(__name__)


class GitHubError(Exception):
    """Raised when the GitHub API returns an unexpected response."""


class RunPhase(enum.StrEnum):
    """Lifecycle phase of a workflow run, as GitHub reports it."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    REQUESTED = "requested"
    PENDING = "pending"


class WorkflowRun(BaseModel):
    """A workflow run as this backend cares about it.

    Attributes:
        id: GitHub run identifier.
        name: Run name, which carries the submission and user key.
        status: Lifecycle phase.
        conclusion: Outcome once completed, otherwise None.
        created_at: When the run was created.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int
    name: str | None
    status: str
    conclusion: str | None
    created_at: datetime.datetime

    @property
    def user_key(self) -> str | None:
        """Extract the user key embedded in the run name.

        Returns:
            The key, or None if the run was not created by this backend.
        """
        if self.name is None:
            return None
        match = RUN_NAME_PATTERN.match(self.name)
        return None if match is None else match.group("user_key")

    @property
    def submission_id(self) -> str | None:
        """Extract the submission identifier embedded in the run name.

        Returns:
            The identifier, or None if the run was not created by this backend.
        """
        if self.name is None:
            return None
        match = RUN_NAME_PATTERN.match(self.name)
        return None if match is None else match.group("submission")

    @property
    def is_active(self) -> bool:
        """Report whether the run is still consuming minutes.

        Returns:
            True while the run is queued or executing.
        """
        return self.status != RunPhase.COMPLETED.value


class _Artifact(BaseModel):
    """An artifact attached to a workflow run.

    Attributes:
        id: Artifact identifier.
        name: Artifact name.
        expired: Whether the artifact has been reclaimed.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int
    name: str
    expired: bool


class GitHubClient:
    """Dispatches benchmark runs and reads their results back."""

    def __init__(
        self,
        *,
        token: str,
        owner: str,
        repo: str,
        ref: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create a client.

        Args:
            token: Fine-grained token scoped to the repository.
            owner: Repository owner.
            repo: Repository name.
            ref: Git ref dispatched runs check out.
            transport: Transport override, used by tests.
        """
        self._owner = owner
        self._repo = repo
        self._ref = ref
        self._client = httpx.AsyncClient(
            base_url=f"{API_ROOT}/repos/{owner}/{repo}",
            headers={
                "authorization": f"Bearer {token}",
                "accept": "application/vnd.github+json",
                "x-github-api-version": API_VERSION,
            },
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
        )

    async def __aenter__(self) -> GitHubClient:
        """Enter the client's context.

        Returns:
            This client.
        """
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close the underlying connection pool."""
        await self._client.aclose()

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._client.aclose()

    async def dispatch(
        self,
        *,
        matrix: DispatchMatrix,
        user_key: str,
        submission_id: str,
        timeout_seconds: int,
    ) -> int:
        """Start a benchmark run.

        The endpoint is documented as returning the run identifier, but
        historically returned an empty body. Both are handled: if no identifier
        comes back, the run is located by the submission identifier embedded in
        its name.

        Args:
            matrix: Legs to execute.
            user_key: Derived key of the requesting user.
            submission_id: Opaque submission identifier.
            timeout_seconds: Per-leg time budget.

        Returns:
            The workflow run identifier.

        Raises:
            GitHubError: If the dispatch failed or the run could not be located.
        """
        response = await self._client.post(
            f"/actions/workflows/{WORKFLOW_FILENAME}/dispatches",
            json={
                "ref": self._ref,
                "inputs": {
                    DispatchInput.MATRIX.value: matrix.model_dump_json(),
                    DispatchInput.USER_KEY.value: user_key,
                    DispatchInput.SUBMISSION_ID.value: submission_id,
                    DispatchInput.TIMEOUT_SECONDS.value: str(timeout_seconds),
                },
            },
        )
        if response.status_code not in {http.HTTPStatus.OK, http.HTTPStatus.NO_CONTENT}:
            raise GitHubError(
                f"dispatch failed with {response.status_code}: {response.text.strip()}"
            )

        if response.status_code == http.HTTPStatus.OK:
            body = response.json()
            run_id = body.get("workflow_run_id")
            if isinstance(run_id, int):
                log.info(
                    "dispatch.accepted",
                    extra={"run_id": run_id, "submission_id": submission_id},
                )
                return run_id

        located = await self.find_run_by_submission(submission_id)
        if located is None:
            raise GitHubError("dispatch was accepted but the run could not be located by name")
        log.info(
            "dispatch.located_by_name",
            extra={"run_id": located, "submission_id": submission_id},
        )
        return located

    async def list_recent_runs(self) -> tuple[WorkflowRun, ...]:
        """List the most recent benchmark runs.

        This single call backs both deduplication and rate limiting; GitHub is
        the only place either piece of state lives.

        Returns:
            The most recent runs, newest first.

        Raises:
            GitHubError: If the listing failed.
        """
        response = await self._client.get(
            f"/actions/workflows/{WORKFLOW_FILENAME}/runs",
            params={"per_page": RUN_PAGE_SIZE},
        )
        if response.status_code != http.HTTPStatus.OK:
            raise GitHubError(
                f"listing runs failed with {response.status_code}: {response.text.strip()}"
            )
        payload = response.json()
        runs: list[WorkflowRun] = []
        for entry in payload.get("workflow_runs", []):
            try:
                runs.append(WorkflowRun.model_validate(entry))
            except ValidationError:
                log.warning("github.unparseable_run")
        return tuple(runs)

    async def find_run_by_submission(self, submission_id: str) -> int | None:
        """Locate a run by the submission identifier in its name.

        Args:
            submission_id: Identifier to search for.

        Returns:
            The run identifier, or None if no run carries it.

        Raises:
            GitHubError: If the listing failed.
        """
        for run in await self.list_recent_runs():
            if run.submission_id == submission_id:
                return run.id
        return None

    async def get_run(self, run_id: int) -> WorkflowRun:
        """Fetch one workflow run.

        Args:
            run_id: Run identifier.

        Returns:
            The run.

        Raises:
            GitHubError: If the run could not be fetched or parsed.
        """
        response = await self._client.get(f"/actions/runs/{run_id}")
        if response.status_code != http.HTTPStatus.OK:
            raise GitHubError(f"fetching run {run_id} failed with {response.status_code}")
        try:
            return WorkflowRun.model_validate(response.json())
        except ValidationError as error:
            raise GitHubError(f"run {run_id} could not be parsed") from error

    async def collect_results(self, *, run_id: int) -> tuple[RunResult, ...]:
        """Download and parse every result artifact attached to a run.

        Each leg uploads its own artifact, so a failed leg still leaves the
        others readable.

        Args:
            run_id: Run identifier.

        Returns:
            Every result that could be read.

        Raises:
            GitHubError: If the artifact listing failed.
        """
        response = await self._client.get(f"/actions/runs/{run_id}/artifacts")
        if response.status_code != http.HTTPStatus.OK:
            raise GitHubError(f"listing artifacts for {run_id} failed with {response.status_code}")

        results: list[RunResult] = []
        for entry in response.json().get("artifacts", []):
            try:
                artifact = _Artifact.model_validate(entry)
            except ValidationError:
                log.warning("github.unparseable_artifact", extra={"run_id": run_id})
                continue
            if artifact.expired is True:
                continue
            if not artifact.name.startswith(ARTIFACT_PREFIX):
                continue
            parsed = await self._download_result(artifact)
            if parsed is not None:
                results.append(parsed)
        return tuple(results)

    async def _download_result(self, artifact: _Artifact) -> RunResult | None:
        """Download one artifact and read the result inside it.

        Args:
            artifact: Artifact to download.

        Returns:
            The parsed result, or None if it could not be read.
        """
        response = await self._client.get(
            f"/actions/artifacts/{artifact.id}/zip", follow_redirects=True
        )
        if response.status_code != http.HTTPStatus.OK:
            log.warning(
                "github.artifact_download_failed",
                extra={"artifact_id": artifact.id, "status": response.status_code},
            )
            return None
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                raw = archive.read(RESULT_FILENAME)
        except zipfile.BadZipFile, KeyError:
            log.warning("github.artifact_unreadable", extra={"artifact_id": artifact.id})
            return None
        try:
            return RunResult.model_validate_json(raw)
        except ValidationError:
            log.warning("github.result_invalid", extra={"artifact_id": artifact.id})
            return None
