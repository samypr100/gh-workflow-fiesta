"""Execution of one benchmark leg against a target interpreter."""

import json
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

import psutil
import structlog
from bench_contract.enums import CpuCountSource, OperatingSystem, RunStatus
from bench_contract.leg import LegKey
from bench_contract.results import Environment, InnerReport, LegError, RunResult

from bench.harness.aggregate import RepeatObservation, aggregate, median_index
from bench.harness.environment import build_target_env
from bench.harness.sampler import Sampler

TARGET_MODULE = "bench.target"
TERMINATE_GRACE_S = 3.0

log = structlog.get_logger(__name__)


class TargetFailedError(Exception):
    """Raised when the target process could not produce a report."""


class TargetTimedOutError(Exception):
    """Raised when the target process exceeded its time budget."""


def _detect_os() -> OperatingSystem:
    """Map the running platform onto the contract's operating system set.

    Returns:
        The matching operating system.

    Raises:
        TargetFailedError: If the platform is not one the benchmark supports.
    """
    match platform.system():
        case "Linux":
            return OperatingSystem.LINUX
        case "Darwin":
            return OperatingSystem.MACOS
        case "Windows":
            return OperatingSystem.WINDOWS
        case other:
            raise TargetFailedError(f"unsupported platform: {other}")


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    """Terminate a process and everything it spawned.

    Args:
        process: The target process.
    """
    try:
        parent = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return
    members = [*parent.children(recursive=True), parent]
    for member in members:
        member.terminate()
    _, alive = psutil.wait_procs(members, timeout=TERMINATE_GRACE_S)
    for member in alive:
        member.kill()


def _run_once(
    leg: LegKey,
    *,
    src_path: str,
    python_executable: str,
    timeout_seconds: float,
    workspace: Path,
) -> RepeatObservation:
    """Execute the target once and collect its measurements.

    Args:
        leg: Leg being executed.
        src_path: Directory placed on the target's `PYTHONPATH`.
        python_executable: Interpreter used to run the target.
        timeout_seconds: Budget for this single execution.
        workspace: Directory for the leg and report files.

    Returns:
        The observation for this repeat.

    Raises:
        TargetTimedOutError: If the budget was exhausted.
        TargetFailedError: If the target exited non-zero or wrote no report.
    """
    leg_path = workspace / "leg.json"
    report_path = workspace / "report.json"
    report_path.unlink(missing_ok=True)
    leg_path.write_text(
        json.dumps(
            {
                "execution_model": leg.execution_model.value,
                "workers": leg.params.workers,
                "iterations": leg.params.iterations,
            }
        ),
        encoding="utf-8",
    )

    env = build_target_env(
        source=os.environ,
        src_path=src_path,
        leg_path=str(leg_path),
        report_path=str(report_path),
        cpu_count_override=leg.cpu_count_override,
    )

    try:
        process = subprocess.Popen(
            [python_executable, "-m", TARGET_MODULE],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        raise TargetFailedError(f"could not start the target interpreter: {error}") from error

    sampler = Sampler(process.pid)
    sampler.start()
    try:
        _, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        samples = sampler.stop()
        raise TargetTimedOutError(
            f"target exceeded the {timeout_seconds:.0f}s budget and was terminated"
        ) from None
    samples = sampler.stop()

    if process.returncode != 0:
        raise TargetFailedError(
            f"target exited with status {process.returncode}: "
            f"{stderr.decode('utf-8', errors='replace').strip()}"
        )
    if not report_path.exists():
        raise TargetFailedError("target exited cleanly but wrote no report")

    report = InnerReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    return RepeatObservation(
        report=report,
        peak_rss_bytes=samples.peak_rss_bytes,
        timeline=samples.points,
    )


def _environment_from(report: InnerReport, leg: LegKey) -> Environment:
    """Describe the runner and interpreter a leg actually ran on.

    Args:
        report: Self-report from the target.
        leg: Leg being executed.

    Returns:
        The environment block.
    """
    source = (
        CpuCountSource.OVERRIDE if leg.cpu_count_override is not None else CpuCountSource.REPORTED
    )
    return Environment(
        runner_os=_detect_os(),
        runner_arch=platform.machine(),
        cpu_model=platform.processor() or "unknown",
        logical_cores=psutil.cpu_count(logical=True) or 1,
        physical_cores=psutil.cpu_count(logical=False),
        total_memory_bytes=psutil.virtual_memory().total,
        python_version=report.python_version,
        python_implementation=report.python_implementation,
        gil_enabled=report.gil_enabled,
        cpu_count_effective=report.cpu_count_effective,
        cpu_count_source=source,
        resolved_interpreter_key=leg.python_key,
    )


def _failed(leg: LegKey, status: RunStatus, kind: str, message: str) -> RunResult:
    """Build a result for a leg that produced no measurements.

    Args:
        leg: Leg being executed.
        status: Terminal status.
        kind: Machine-readable failure category.
        message: Human-readable detail.

    Returns:
        The result.
    """
    return RunResult(
        leg=leg,
        status=status,
        environment=None,
        scalars=None,
        timeline=[],
        phases=[],
        error=LegError(kind=kind, message=message),
    )


def run_leg(
    leg: LegKey,
    *,
    src_path: str,
    python_executable: str,
    timeout_seconds: float,
) -> RunResult:
    """Execute every repeat of a leg and assemble its result.

    Repeats share the time budget rather than each receiving it. Once the
    remaining budget cannot accommodate another repeat, the runner stops and
    reports however many completed.

    Args:
        leg: Leg to execute.
        src_path: Directory placed on the target's `PYTHONPATH`.
        python_executable: Interpreter used to run the target.
        timeout_seconds: Total budget for the leg.

    Returns:
        The result, whatever the outcome. This function does not raise.
    """
    observations: list[RepeatObservation] = []
    deadline = time.perf_counter() + timeout_seconds

    with tempfile.TemporaryDirectory(prefix="bench-") as raw_workspace:
        workspace = Path(raw_workspace)
        for attempt in range(leg.params.repeats):
            remaining = deadline - time.perf_counter()
            if remaining <= 0.0:
                break
            try:
                observations.append(
                    _run_once(
                        leg,
                        src_path=src_path,
                        python_executable=python_executable,
                        timeout_seconds=remaining,
                        workspace=workspace,
                    )
                )
            except TargetTimedOutError as error:
                log.warning("leg.timed_out", extra={"leg_id": leg.leg_id})
                if len(observations) == 0:
                    return _failed(leg, RunStatus.TIMEOUT, "Timeout", str(error))
                break
            except TargetFailedError as error:
                log.warning("leg.failed", extra={"leg_id": leg.leg_id, "attempt": attempt})
                if len(observations) == 0:
                    return _failed(leg, RunStatus.ERROR, "TargetFailed", str(error))
                break

    if len(observations) == 0:
        return _failed(leg, RunStatus.ERROR, "NoRepeats", "the time budget allowed no repeats")

    representative = observations[median_index(observations)]
    return RunResult(
        leg=leg,
        status=RunStatus.OK,
        environment=_environment_from(representative.report, leg),
        scalars=aggregate(observations),
        timeline=representative.timeline,
        phases=list(representative.report.phases),
        error=None,
    )
