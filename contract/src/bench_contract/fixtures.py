"""Representative results used by downstream test suites.

These exist so the backend and frontend can be developed and tested without
dispatching a real workflow run.
"""

from bench_contract.enums import (
    CpuCountSource,
    ExecutionModel,
    OperatingSystem,
    RunStatus,
    Variant,
    WorkloadKind,
)
from bench_contract.leg import LegKey
from bench_contract.params import WorkloadParams
from bench_contract.results import (
    Environment,
    LegError,
    Phase,
    RunResult,
    Scalars,
    ScalarStats,
    TimelinePoint,
)

_PARAMS = WorkloadParams(workers=4, iterations=200_000)


def _environment(
    *,
    python_version: str,
    gil_enabled: bool,
    key: str,
    os_: OperatingSystem = OperatingSystem.LINUX,
    arch: str = "x86_64",
) -> Environment:
    """Build an Environment for a fixture.

    Args:
        python_version: Version string to report.
        gil_enabled: GIL state to report.
        key: Resolved interpreter key.
        os_: Runner operating system.
        arch: Runner architecture.

    Returns:
        The environment.
    """
    return Environment(
        runner_os=os_,
        runner_arch=arch,
        cpu_model="AMD EPYC 7763 64-Core Processor",
        logical_cores=4,
        physical_cores=2,
        total_memory_bytes=16_777_216_000,
        python_version=python_version,
        python_implementation="CPython",
        gil_enabled=gil_enabled,
        cpu_count_effective=4,
        cpu_count_source=CpuCountSource.OVERRIDE,
        resolved_interpreter_key=key,
    )


def _timeline(peak_cpu: float) -> list[TimelinePoint]:
    """Build a short synthetic sampling timeline.

    Args:
        peak_cpu: CPU percentage at the plateau.

    Returns:
        Five evenly spaced samples.
    """
    shape = (0.0, peak_cpu, peak_cpu, peak_cpu, 0.0)
    return [
        TimelinePoint(
            t_s=round(index * 0.1, 1),
            cpu_percent=value,
            num_threads=5,
            rss_bytes=20_000_000 + index * 250_000,
        )
        for index, value in enumerate(shape)
    ]


def _gil_threading_result() -> RunResult:
    """Threads on a GIL-enabled build: no effective parallelism.

    Returns:
        The result.
    """
    return RunResult(
        leg=LegKey(
            os=OperatingSystem.LINUX,
            arch="x86_64",
            python_key="cpython-3.14.7-linux-x86_64-gnu",
            variant=Variant.DEFAULT,
            workload=WorkloadKind.CPU_BOUND,
            execution_model=ExecutionModel.THREADING,
            params=_PARAMS,
            cpu_count_override=4,
        ),
        status=RunStatus.OK,
        environment=_environment(
            python_version="3.14.7",
            gil_enabled=True,
            key="cpython-3.14.7-linux-x86_64-gnu",
        ),
        scalars=Scalars(
            wall_time_s=ScalarStats(median=4.02, minimum=3.95, maximum=4.20),
            cpu_user_s=ScalarStats(median=4.05, minimum=3.98, maximum=4.24),
            cpu_sys_s=ScalarStats(median=0.06, minimum=0.04, maximum=0.09),
            parallelism_factor=ScalarStats(median=1.02, minimum=1.00, maximum=1.05),
            peak_rss_bytes=ScalarStats(
                median=21_500_000.0, minimum=21_000_000.0, maximum=22_100_000.0
            ),
            throughput_ops_s=ScalarStats(median=199_004.0, minimum=190_476.0, maximum=202_531.0),
            repeats_completed=3,
        ),
        timeline=_timeline(102.0),
        phases=[
            Phase(name="setup", duration_s=0.01),
            Phase(name="work", duration_s=3.99),
            Phase(name="join", duration_s=0.02),
        ],
        error=None,
    )


def _freethreaded_threading_result() -> RunResult:
    """Threads on a free-threaded build: real parallelism.

    Returns:
        The result.
    """
    return RunResult(
        leg=LegKey(
            os=OperatingSystem.LINUX,
            arch="x86_64",
            python_key="cpython-3.14.7+freethreaded-linux-x86_64-gnu",
            variant=Variant.FREETHREADED,
            workload=WorkloadKind.CPU_BOUND,
            execution_model=ExecutionModel.THREADING,
            params=_PARAMS,
            cpu_count_override=4,
        ),
        status=RunStatus.OK,
        environment=_environment(
            python_version="3.14.7",
            gil_enabled=False,
            key="cpython-3.14.7+freethreaded-linux-x86_64-gnu",
        ),
        scalars=Scalars(
            wall_time_s=ScalarStats(median=1.21, minimum=1.15, maximum=1.33),
            cpu_user_s=ScalarStats(median=4.51, minimum=4.40, maximum=4.70),
            cpu_sys_s=ScalarStats(median=0.10, minimum=0.08, maximum=0.14),
            parallelism_factor=ScalarStats(median=3.81, minimum=3.62, maximum=3.94),
            peak_rss_bytes=ScalarStats(
                median=27_800_000.0, minimum=27_100_000.0, maximum=28_400_000.0
            ),
            throughput_ops_s=ScalarStats(median=661_157.0, minimum=601_503.0, maximum=695_652.0),
            repeats_completed=3,
        ),
        timeline=_timeline(381.0),
        phases=[
            Phase(name="setup", duration_s=0.01),
            Phase(name="work", duration_s=1.18),
            Phase(name="join", duration_s=0.02),
        ],
        error=None,
    )


def _timeout_result() -> RunResult:
    """A leg that exceeded its time budget but kept partial samples.

    Returns:
        The result.
    """
    return RunResult(
        leg=LegKey(
            os=OperatingSystem.WINDOWS,
            arch="x86_64",
            python_key="cpython-3.13.15-windows-x86_64-none",
            variant=Variant.DEFAULT,
            workload=WorkloadKind.CPU_BOUND,
            execution_model=ExecutionModel.SEQUENTIAL,
            params=WorkloadParams(workers=1, iterations=10_000_000),
            cpu_count_override=4,
        ),
        status=RunStatus.TIMEOUT,
        environment=_environment(
            python_version="3.13.15",
            gil_enabled=True,
            key="cpython-3.13.15-windows-x86_64-none",
            os_=OperatingSystem.WINDOWS,
        ),
        scalars=None,
        timeline=_timeline(100.0),
        phases=[],
        error=LegError(
            kind="Timeout",
            message="target process exceeded the 300s budget and was terminated",
        ),
    )


def _error_result() -> RunResult:
    """A leg whose interpreter never installed.

    Returns:
        The result.
    """
    return RunResult(
        leg=LegKey(
            os=OperatingSystem.MACOS,
            arch="aarch64",
            python_key="cpython-3.15.0rc2+freethreaded-macos-aarch64-none",
            variant=Variant.FREETHREADED,
            workload=WorkloadKind.CPU_BOUND,
            execution_model=ExecutionModel.SUBINTERPRETERS,
            params=_PARAMS,
            cpu_count_override=3,
        ),
        status=RunStatus.ERROR,
        environment=None,
        scalars=None,
        timeline=[],
        phases=[],
        error=LegError(
            kind="InterpreterInstallFailed",
            message="uv python install exited with status 1",
        ),
    )


def sample_results() -> tuple[RunResult, ...]:
    """Return one representative result per interesting outcome.

    Returns:
        A GIL-enabled threading run, a free-threaded threading run, a timeout,
        and an install failure.
    """
    return (
        _gil_threading_result(),
        _freethreaded_threading_result(),
        _timeout_result(),
        _error_result(),
    )
