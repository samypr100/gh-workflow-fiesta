"""Policy for accepting submissions and reporting their progress."""

import datetime
import uuid

import structlog
from bench_contract.catalog import (
    CATALOG,
    find_entry,
    python_minor_from_key,
    supports_version,
)
from bench_contract.dispatch import build_matrix
from bench_contract.enums import Variant
from bench_contract.leg import LegKey
from bench_contract.params import DEFAULT_REPEATS

from proxy_be.admission import AdmissionVerdict, check_admission
from proxy_be.github import GitHubClient, GitHubError, RunPhase
from proxy_be.interpreters import RUNNER_TARGETS, InterpreterCache
from proxy_be.schemas import (
    ApiRunPhase,
    CatalogItem,
    CatalogResponse,
    CreateRunResponse,
    InterpretersResponse,
    RunnerInfo,
    RunnersResponse,
    RunStatusResponse,
    SelectionRequest,
)
from proxy_be.settings import Settings
from proxy_be.tokens import (
    InvalidRunToken,
    RunTokenPayload,
    derive_user_key,
    sign_run_token,
    verify_run_token,
)

DEFAULT_WORKERS = 4
DEFAULT_ITERATIONS = 1_000_000

# Documented logical core counts for the standard runner images. Used only to
# pick the CPU count every leg is normalised to; the measured value always
# comes back in the result's environment block.
RUNNER_CORES = {
    "ubuntu-latest": 4,
    "windows-latest": 4,
    "macos-latest": 3,
}

log = structlog.get_logger(__name__)


class SubmissionRejected(Exception):  # noqa: N818
    """Raised when a submission cannot be accepted.

    Attributes:
        verdict: Admission verdict, when the rejection came from admission control.
        retry_after_seconds: Seconds to wait, when the rejection was a rate limit.
    """

    def __init__(
        self,
        message: str,
        *,
        verdict: AdmissionVerdict | None = None,
        retry_after_seconds: int = 0,
    ) -> None:
        """Create the exception.

        Args:
            message: Human-readable explanation.
            verdict: Admission verdict, if applicable.
            retry_after_seconds: Seconds to wait, if applicable.
        """
        super().__init__(message)
        self.verdict = verdict
        self.retry_after_seconds = retry_after_seconds


class BenchmarkService:
    """Accepts submissions, dispatches them, and reports their progress."""

    def __init__(self, *, settings: Settings, github: GitHubClient) -> None:
        """Create the service.

        Args:
            settings: Runtime configuration.
            github: Client for the benchmark repository.
        """
        self._settings = settings
        self._github = github
        self._interpreters = InterpreterCache(
            uv_executable=settings.uv_executable,
            ttl_seconds=settings.interpreter_cache_ttl_seconds,
        )

    async def aclose(self) -> None:
        """Release the underlying GitHub connection pool."""
        await self._github.aclose()

    def catalog(self) -> CatalogResponse:
        """Return everything a user may select.

        Returns:
            The catalog.
        """
        return CatalogResponse(
            items=[
                CatalogItem(
                    workload=entry.workload,
                    execution_model=entry.execution_model,
                    minimum_python_minor=entry.minimum_python_minor,
                    title=entry.title,
                    explainer=entry.explainer,
                    expectation=entry.expectation,
                )
                for entry in CATALOG
            ],
            default_workers=DEFAULT_WORKERS,
            default_iterations=DEFAULT_ITERATIONS,
        )

    async def interpreters(self) -> InterpretersResponse:
        """Return the interpreters a runner can execute.

        Returns:
            The interpreter list.
        """
        options = await self._interpreters.get()
        return InterpretersResponse(interpreters=list(options))

    def runners(self) -> RunnersResponse:
        """Return the runner images users may target.

        Returns:
            The runner list.
        """
        return RunnersResponse(
            runners=[
                RunnerInfo(
                    os=target.os,
                    arch=target.arch,
                    logical_cores=RUNNER_CORES[target.image],
                )
                for target in RUNNER_TARGETS
            ]
        )

    def _cpu_count_for(self, selections: list[SelectionRequest]) -> int:
        """Choose the CPU count every leg is normalised to.

        Runner images differ in core count, so worker pools would otherwise be
        sized differently per operating system and the comparison would be
        quietly unfair. The minimum across the selected images is used.

        Args:
            selections: Configurations in the submission.

        Returns:
            The CPU count to force through `PYTHON_CPU_COUNT`.
        """
        chosen = {selection.os for selection in selections}
        cores = [RUNNER_CORES[target.image] for target in RUNNER_TARGETS if target.os in chosen]
        return min(cores)

    def _to_leg(self, selection: SelectionRequest, cpu_count: int) -> LegKey:
        """Validate one selection and convert it into a leg.

        Args:
            selection: Configuration requested by the user.
            cpu_count: CPU count to normalise to.

        Returns:
            The leg.

        Raises:
            SubmissionRejected: If the combination is not shipped, or the
                interpreter is too old to support it.
        """
        entry = find_entry(selection.workload, selection.execution_model)
        if entry is None:
            raise SubmissionRejected(
                f"{selection.workload.value} with {selection.execution_model.value} "
                "is not an available combination"
            )

        minor = python_minor_from_key(selection.python_key)
        if supports_version(entry, minor) is False:
            raise SubmissionRejected(
                f"{entry.title} requires Python 3.{entry.minimum_python_minor} or "
                f"newer, but 3.{minor} was selected"
            )

        target = next((item for item in RUNNER_TARGETS if item.os is selection.os), None)
        if target is None:
            raise SubmissionRejected(f"no runner provides {selection.os.value}")

        variant = (
            Variant.FREETHREADED if "+freethreaded" in selection.python_key else Variant.DEFAULT
        )
        return LegKey(
            os=selection.os,
            arch=target.arch,
            python_key=selection.python_key,
            variant=variant,
            workload=selection.workload,
            execution_model=selection.execution_model,
            params=selection.to_params(DEFAULT_REPEATS),
            cpu_count_override=cpu_count,
        )

    async def create_run(
        self,
        *,
        selections: list[SelectionRequest],
        client_ip: str,
        now: datetime.datetime,
    ) -> CreateRunResponse:
        """Validate a submission, check admission, and dispatch it.

        Args:
            selections: Configurations to compare.
            client_ip: Address the request came from.
            now: Current time.

        Returns:
            The run token and leg count.

        Raises:
            SubmissionRejected: If the submission is invalid, duplicated, rate
                limited, or could not be dispatched.
        """
        cpu_count = self._cpu_count_for(selections)
        legs = [self._to_leg(selection, cpu_count) for selection in selections]

        user_key = derive_user_key(
            client_ip, secret=self._settings.user_key_secret.get_secret_value()
        )
        try:
            recent = await self._github.list_recent_runs()
        except GitHubError as error:
            raise SubmissionRejected("could not reach GitHub") from error

        decision = check_admission(
            runs=recent,
            user_key=user_key,
            now=now,
            window_seconds=self._settings.rate_limit_window_seconds,
            max_runs=self._settings.rate_limit_max_runs,
        )
        if decision.verdict is AdmissionVerdict.DUPLICATE:
            raise SubmissionRejected(
                "you already have a benchmark run in progress",
                verdict=decision.verdict,
            )
        if decision.verdict is AdmissionVerdict.RATE_LIMITED:
            raise SubmissionRejected(
                "too many benchmark runs started recently",
                verdict=decision.verdict,
                retry_after_seconds=decision.retry_after_seconds,
            )

        submission_id = uuid.uuid4().hex[:12]
        try:
            run_id = await self._github.dispatch(
                matrix=build_matrix(legs),
                user_key=user_key,
                submission_id=submission_id,
                timeout_seconds=self._settings.leg_timeout_seconds,
            )
        except GitHubError as error:
            raise SubmissionRejected("could not start the benchmark run") from error

        token = sign_run_token(
            RunTokenPayload(
                run_id=run_id,
                submission_id=submission_id,
                user_key=user_key,
                expires_at=int(now.timestamp()) + self._settings.run_token_ttl_seconds,
            ),
            secret=self._settings.token_secret.get_secret_value(),
        )
        log.info(
            "submission.dispatched",
            extra={
                "run_id": run_id,
                "submission_id": submission_id,
                "leg_count": len(legs),
            },
        )
        return CreateRunResponse(run_token=token, leg_count=len(legs))

    async def run_status(self, run_token: str, *, now: int) -> RunStatusResponse:
        """Report progress and results for a submitted run.

        Args:
            run_token: Token issued when the run was created.
            now: Current Unix timestamp.

        Returns:
            The current phase and whatever results exist.

        Raises:
            SubmissionRejected: If the token is invalid or GitHub is unreachable.
        """
        try:
            payload = verify_run_token(
                run_token,
                secret=self._settings.token_secret.get_secret_value(),
                now=now,
            )
        except InvalidRunToken as error:
            raise SubmissionRejected("this run token is not valid") from error

        try:
            run = await self._github.get_run(payload.run_id)
        except GitHubError as error:
            raise SubmissionRejected("could not reach GitHub") from error

        results = await self._github.collect_results(run_id=payload.run_id)
        expected = len(results)

        if run.status != RunPhase.COMPLETED.value:
            phase = ApiRunPhase.RUNNING if len(results) > 0 else ApiRunPhase.PENDING
            return RunStatusResponse(phase=phase, expected_legs=expected, results=list(results))

        if len(results) == 0:
            return RunStatusResponse(
                phase=ApiRunPhase.FAILED,
                expected_legs=0,
                results=[],
                detail="the run finished but produced no results",
            )
        return RunStatusResponse(
            phase=ApiRunPhase.COMPLETE, expected_legs=expected, results=list(results)
        )
