"""Measurements produced by one benchmark leg."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from bench_contract.enums import CpuCountSource, OperatingSystem, RunStatus
from bench_contract.leg import LegKey


class ScalarStats(BaseModel):
    """Spread of one metric across the repeats of a leg.

    Attributes:
        median: Reported central value.
        minimum: Smallest observation.
        maximum: Largest observation.
    """

    model_config = ConfigDict(frozen=True)

    median: float
    minimum: float
    maximum: float

    @model_validator(mode="after")
    def check_bounds(self) -> Self:
        """Ensure the median lies within the observed range.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the bounds are inconsistent.
        """
        if self.minimum > self.maximum:
            raise ValueError("minimum exceeds maximum")
        if not (self.minimum <= self.median <= self.maximum):
            raise ValueError("median lies outside the observed range")
        return self


class Scalars(BaseModel):
    """Aggregate scalar metrics for a leg.

    Timing values originate from the target's own `os.times()` and
    `perf_counter`; `peak_rss_bytes` originates from the harness's outside
    sampler, which is the only one of the two that can observe it portably.

    Attributes:
        wall_time_s: Duration of the measured work, excluding interpreter startup.
        cpu_user_s: User-mode CPU time across all threads of the target.
        cpu_sys_s: Kernel-mode CPU time across all threads of the target.
        parallelism_factor: Total CPU time divided by wall time. Near 1.0 means
            no effective parallelism; near the worker count means full parallelism.
        peak_rss_bytes: Peak resident set size, in bytes.
        throughput_ops_s: Operations per second, or None if the workload does not
            report an operation count.
        repeats_completed: How many repeats finished within the time budget.
    """

    model_config = ConfigDict(frozen=True)

    wall_time_s: ScalarStats
    cpu_user_s: ScalarStats
    cpu_sys_s: ScalarStats
    parallelism_factor: ScalarStats
    peak_rss_bytes: ScalarStats
    throughput_ops_s: ScalarStats | None
    repeats_completed: int


class Environment(BaseModel):
    """Runner and interpreter facts needed to interpret a measurement fairly.

    Attributes:
        runner_os: Operating system of the runner image.
        runner_arch: Architecture of the runner image.
        cpu_model: Human-readable processor description.
        logical_cores: Logical cores the runner exposes.
        physical_cores: Physical cores, or None when the platform cannot report it.
        total_memory_bytes: Total system memory, in bytes.
        python_version: Version string reported by the target interpreter.
        python_implementation: Implementation name reported by the target.
        gil_enabled: Whether the GIL was active during the run.
        cpu_count_effective: CPU count the interpreter actually reported.
        cpu_count_source: Whether that count was observed or forced.
        resolved_interpreter_key: uv key uv actually resolved and installed.
    """

    model_config = ConfigDict(frozen=True)

    runner_os: OperatingSystem
    runner_arch: str
    cpu_model: str
    logical_cores: int
    physical_cores: int | None
    total_memory_bytes: int
    python_version: str
    python_implementation: str
    gil_enabled: bool
    cpu_count_effective: int
    cpu_count_source: CpuCountSource
    resolved_interpreter_key: str


class TimelinePoint(BaseModel):
    """One sample taken by the harness while the target ran.

    Attributes:
        t_s: Seconds since the target process started.
        cpu_percent: CPU utilisation of the process tree at this sample.
        num_threads: Thread count observed at this sample.
        rss_bytes: Resident set size at this sample, in bytes.
    """

    model_config = ConfigDict(frozen=True)

    t_s: float
    cpu_percent: float
    num_threads: int
    rss_bytes: int


class Phase(BaseModel):
    """A self-reported segment of the workload.

    Attributes:
        name: Phase label, for example `setup`, `work`, or `join`.
        duration_s: Duration of the phase.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    duration_s: float


class LegError(BaseModel):
    """Why a leg failed to produce measurements.

    Attributes:
        kind: Stable machine-readable category.
        message: Human-readable detail.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    message: str


class InnerReport(BaseModel):
    """Self-reported detail written by the target interpreter.

    The target measures its own timings because `os.times()` gives an exact
    user and system split that is portable to Windows, and because excluding
    interpreter startup keeps the comparison about the workload rather than
    about how long each build takes to boot.

    Attributes:
        phases: Phase timings measured inside the workload.
        operations: Operation count for throughput, or None if not applicable.
        wall_time_s: Duration of the measured work, excluding interpreter startup.
        cpu_user_s: User-mode CPU time consumed by the work, across all threads.
        cpu_sys_s: Kernel-mode CPU time consumed by the work, across all threads.
        gil_enabled: GIL state observed inside the target.
        python_version: Version observed inside the target.
        python_implementation: Implementation observed inside the target.
        cpu_count_effective: CPU count the target interpreter reported.
    """

    model_config = ConfigDict(frozen=True)

    phases: list[Phase]
    operations: int | None
    wall_time_s: float
    cpu_user_s: float
    cpu_sys_s: float
    gil_enabled: bool
    python_version: str
    python_implementation: str
    cpu_count_effective: int


class RunResult(BaseModel):
    """Complete outcome of one benchmark leg.

    Attributes:
        leg: Identity of the leg these measurements belong to.
        status: Terminal state of the leg.
        environment: Runner and interpreter facts, or None if the target never started.
        scalars: Aggregate metrics, or None when the leg produced no complete repeat.
        timeline: Samples from the repeat whose wall time was the median.
        phases: Self-reported phase timings from that same repeat.
        error: Failure detail, or None when the leg succeeded.
    """

    model_config = ConfigDict(frozen=True)

    leg: LegKey
    status: RunStatus
    environment: Environment | None
    scalars: Scalars | None
    timeline: list[TimelinePoint]
    phases: list[Phase]
    error: LegError | None

    @model_validator(mode="after")
    def check_status_consistency(self) -> Self:
        """Ensure the payload matches the declared status.

        Returns:
            The validated instance.

        Raises:
            ValueError: If a successful leg lacks measurements, or a failed leg
                lacks an error.
        """
        if self.status is RunStatus.OK and self.scalars is None:
            raise ValueError("a successful leg must carry scalars")
        if self.status is not RunStatus.OK and self.error is None:
            raise ValueError("a non-successful leg must carry an error")
        return self
