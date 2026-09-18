"""Tests for benchmark result models."""

import pytest
from pydantic import ValidationError

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
    InnerReport,
    LegError,
    RunResult,
    ScalarStats,
    Scalars,
    TimelinePoint,
)


def make_leg() -> LegKey:
    return LegKey(
        os=OperatingSystem.LINUX,
        arch="x86_64",
        python_key="cpython-3.14.7-linux-x86_64-gnu",
        variant=Variant.DEFAULT,
        workload=WorkloadKind.CPU_BOUND,
        execution_model=ExecutionModel.THREADING,
        params=WorkloadParams(workers=4, iterations=1000),
    )


def make_environment() -> Environment:
    return Environment(
        runner_os=OperatingSystem.LINUX,
        runner_arch="x86_64",
        cpu_model="AMD EPYC 7763",
        logical_cores=4,
        physical_cores=2,
        total_memory_bytes=16_777_216_000,
        python_version="3.14.7",
        python_implementation="CPython",
        gil_enabled=True,
        cpu_count_effective=4,
        cpu_count_source=CpuCountSource.REPORTED,
        resolved_interpreter_key="cpython-3.14.7-linux-x86_64-gnu",
    )


def test_scalar_stats_rejects_inverted_bounds() -> None:
    with pytest.raises(ValidationError):
        ScalarStats(median=1.0, minimum=2.0, maximum=3.0)


def test_scalar_stats_accepts_ordered_bounds() -> None:
    stats = ScalarStats(median=2.0, minimum=1.0, maximum=3.0)
    assert stats.median == 2.0


def test_ok_result_requires_scalars() -> None:
    with pytest.raises(ValidationError):
        RunResult(
            leg=make_leg(),
            status=RunStatus.OK,
            environment=make_environment(),
            scalars=None,
            timeline=[],
            phases=[],
            error=None,
        )


def test_error_result_requires_an_error() -> None:
    with pytest.raises(ValidationError):
        RunResult(
            leg=make_leg(),
            status=RunStatus.ERROR,
            environment=None,
            scalars=None,
            timeline=[],
            phases=[],
            error=None,
        )


def test_error_result_round_trips() -> None:
    result = RunResult(
        leg=make_leg(),
        status=RunStatus.ERROR,
        environment=None,
        scalars=None,
        timeline=[],
        phases=[],
        error=LegError(kind="InterpreterInstallFailed", message="uv exited with 1"),
    )
    restored = RunResult.model_validate_json(result.model_dump_json())
    assert restored.error is not None
    assert restored.error.kind == "InterpreterInstallFailed"


def test_timeout_result_keeps_its_partial_timeline() -> None:
    result = RunResult(
        leg=make_leg(),
        status=RunStatus.TIMEOUT,
        environment=make_environment(),
        scalars=None,
        timeline=[TimelinePoint(t_s=0.1, cpu_percent=99.5, num_threads=5, rss_bytes=1024)],
        phases=[],
        error=LegError(kind="Timeout", message="exceeded 300s"),
    )
    assert len(result.timeline) == 1


def test_inner_report_parses_plain_json() -> None:
    report = InnerReport.model_validate_json(
        '{"phases": [{"name": "work", "duration_s": 1.5}], "operations": 4000,'
        ' "wall_time_s": 1.5, "cpu_user_s": 5.8, "cpu_sys_s": 0.1,'
        ' "gil_enabled": false, "python_version": "3.14.7",'
        ' "python_implementation": "CPython", "cpu_count_effective": 4}'
    )
    assert report.operations == 4000
    assert report.gil_enabled is False
    assert report.cpu_user_s == 5.8


def test_scalars_carry_repeat_count() -> None:
    scalars = Scalars(
        wall_time_s=ScalarStats(median=1.0, minimum=0.9, maximum=1.1),
        cpu_user_s=ScalarStats(median=3.8, minimum=3.7, maximum=3.9),
        cpu_sys_s=ScalarStats(median=0.1, minimum=0.1, maximum=0.2),
        parallelism_factor=ScalarStats(median=3.9, minimum=3.8, maximum=4.0),
        peak_rss_bytes=ScalarStats(median=1024.0, minimum=1024.0, maximum=2048.0),
        throughput_ops_s=None,
        repeats_completed=3,
    )
    assert scalars.repeats_completed == 3
