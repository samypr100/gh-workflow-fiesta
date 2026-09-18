"""Request and response shapes for the public API.

The frontend's TypeScript types are generated from these, so a name chosen
here is the name the frontend uses.
"""

import enum

from bench_contract.dispatch import MAX_MATRIX_JOBS
from bench_contract.enums import ExecutionModel, OperatingSystem, WorkloadKind
from bench_contract.params import MAX_ITERATIONS, MAX_WORKERS, WorkloadParams
from bench_contract.results import RunResult
from pydantic import BaseModel, ConfigDict, Field

from proxy_be.interpreters import InterpreterOption


class ApiRunPhase(enum.StrEnum):
    """Lifecycle phase reported to the frontend."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class CatalogItem(BaseModel):
    """A selectable workload and execution model.

    Attributes:
        workload: Nature of the work.
        execution_model: Concurrency strategy.
        minimum_python_minor: Lowest supported Python 3.x minor version.
        title: Short label for the interface.
        explainer: What this combination does.
        expectation: What the measurement should look like.
    """

    model_config = ConfigDict(frozen=True)

    workload: WorkloadKind
    execution_model: ExecutionModel
    minimum_python_minor: int
    title: str
    explainer: str
    expectation: str


class CatalogResponse(BaseModel):
    """Everything a user may select.

    Attributes:
        items: Available workload and execution model combinations.
        default_workers: Suggested worker count.
        default_iterations: Suggested iteration count.
        max_workers: Largest permitted worker count.
        max_iterations: Largest permitted iteration count.
    """

    model_config = ConfigDict(frozen=True)

    items: list[CatalogItem]
    default_workers: int
    default_iterations: int
    max_workers: int = MAX_WORKERS
    max_iterations: int = MAX_ITERATIONS


class RunnerInfo(BaseModel):
    """A runner image users may target.

    Attributes:
        os: Operating system the image provides.
        arch: Architecture the image provides.
        logical_cores: Cores the image is documented to provide, used to
            compute the default CPU count normalisation.
    """

    model_config = ConfigDict(frozen=True)

    os: OperatingSystem
    arch: str
    logical_cores: int


class RunnersResponse(BaseModel):
    """Available runner images.

    Attributes:
        runners: One entry per supported operating system.
    """

    model_config = ConfigDict(frozen=True)

    runners: list[RunnerInfo]


class InterpretersResponse(BaseModel):
    """Selectable interpreters.

    Attributes:
        interpreters: Every interpreter a runner can execute.
    """

    model_config = ConfigDict(frozen=True)

    interpreters: list[InterpreterOption]


class SelectionRequest(BaseModel):
    """One configuration a user added to their comparison.

    Attributes:
        os: Operating system to run on.
        python_key: Full uv interpreter key.
        workload: Nature of the work.
        execution_model: Concurrency strategy.
        workers: Number of concurrent units.
        iterations: Units of work per worker.
    """

    model_config = ConfigDict(frozen=True)

    os: OperatingSystem
    python_key: str
    workload: WorkloadKind
    execution_model: ExecutionModel
    workers: int = Field(ge=1, le=MAX_WORKERS)
    iterations: int = Field(ge=1, le=MAX_ITERATIONS)

    def to_params(self, repeats: int) -> WorkloadParams:
        """Convert this selection's tunables into workload parameters.

        Args:
            repeats: Number of repeats to request.

        Returns:
            The parameters.
        """
        return WorkloadParams(workers=self.workers, iterations=self.iterations, repeats=repeats)


class CreateRunRequest(BaseModel):
    """A submission.

    Attributes:
        selections: Configurations to compare.
    """

    model_config = ConfigDict(frozen=True)

    selections: list[SelectionRequest] = Field(min_length=1, max_length=MAX_MATRIX_JOBS)


class CreateRunResponse(BaseModel):
    """Acknowledgement of an accepted submission.

    Attributes:
        run_token: Opaque token the frontend polls with and stores locally.
        leg_count: How many legs were dispatched.
    """

    model_config = ConfigDict(frozen=True)

    run_token: str
    leg_count: int


class RunStatusResponse(BaseModel):
    """Progress and results for a submitted run.

    Attributes:
        phase: Lifecycle phase.
        expected_legs: How many legs the submission dispatched.
        results: Results collected so far, growing as legs finish.
        detail: Human-readable explanation when the phase is a failure.
    """

    model_config = ConfigDict(frozen=True)

    phase: ApiRunPhase
    expected_legs: int
    results: list[RunResult]
    detail: str | None = None
