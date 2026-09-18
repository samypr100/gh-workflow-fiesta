"""Tests for the workflow dispatch contract."""

import json

from bench_contract.dispatch import (
    DispatchInput,
    RUNNER_IMAGES,
    artifact_name,
    build_matrix,
)
from bench_contract.enums import ExecutionModel, OperatingSystem, Variant, WorkloadKind
from bench_contract.leg import LegKey
from bench_contract.params import WorkloadParams


def make_leg(os_: OperatingSystem = OperatingSystem.LINUX) -> LegKey:
    return LegKey(
        os=os_,
        arch="x86_64",
        python_key="cpython-3.14.7-linux-x86_64-gnu",
        variant=Variant.DEFAULT,
        workload=WorkloadKind.CPU_BOUND,
        execution_model=ExecutionModel.THREADING,
        params=WorkloadParams(workers=4, iterations=1000),
    )


def test_every_operating_system_maps_to_a_runner_image() -> None:
    assert set(RUNNER_IMAGES) == set(OperatingSystem)


def test_artifact_name_is_prefixed() -> None:
    assert artifact_name("linux-threading-abcd1234") == "result-linux-threading-abcd1234"


def test_matrix_include_carries_the_runner_image() -> None:
    matrix = build_matrix([make_leg(OperatingSystem.MACOS)])
    assert matrix.include[0].runs_on == "macos-latest"


def test_leg_json_round_trips_through_the_matrix() -> None:
    leg = make_leg()
    matrix = build_matrix([leg])
    restored = LegKey.model_validate_json(matrix.include[0].leg_json)
    assert restored.leg_id == leg.leg_id


def test_matrix_serialises_to_json_github_can_parse() -> None:
    matrix = build_matrix([make_leg()])
    decoded = json.loads(matrix.model_dump_json())
    assert isinstance(decoded["include"], list)
    assert set(decoded["include"][0]) == {"leg_id", "runs_on", "python_key", "leg_json"}


def test_dispatch_input_names_are_stable() -> None:
    assert {member.value for member in DispatchInput} == {
        "matrix",
        "user_key",
        "submission_id",
        "timeout_seconds",
    }
