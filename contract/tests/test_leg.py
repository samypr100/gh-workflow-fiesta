"""Tests for leg identity."""

import re

from bench_contract.enums import ExecutionModel, OperatingSystem, Variant, WorkloadKind
from bench_contract.leg import LegKey
from bench_contract.params import WorkloadParams


def make_leg(**overrides: object) -> LegKey:
    defaults: dict[str, object] = {
        "os": OperatingSystem.LINUX,
        "arch": "x86_64",
        "python_key": "cpython-3.14.7-linux-x86_64-gnu",
        "variant": Variant.DEFAULT,
        "workload": WorkloadKind.CPU_BOUND,
        "execution_model": ExecutionModel.THREADING,
        "params": WorkloadParams(workers=4, iterations=1000),
    }
    return LegKey(**(defaults | overrides))


def test_leg_id_is_deterministic() -> None:
    assert make_leg().leg_id == make_leg().leg_id


def test_leg_id_changes_with_any_field() -> None:
    baseline = make_leg().leg_id
    assert make_leg(arch="aarch64").leg_id != baseline
    assert make_leg(variant=Variant.FREETHREADED).leg_id != baseline
    assert make_leg(params=WorkloadParams(workers=8, iterations=1000)).leg_id != baseline
    assert make_leg(cpu_count_override=2).leg_id != baseline


def test_leg_id_is_artifact_name_safe() -> None:
    assert re.fullmatch(r"[a-z0-9_-]+", make_leg().leg_id) is not None


def test_leg_id_is_readable() -> None:
    assert make_leg().leg_id.startswith("linux-threading-")


def test_leg_id_survives_a_serialisation_round_trip() -> None:
    original = make_leg()
    restored = LegKey.model_validate_json(original.model_dump_json())
    assert restored.leg_id == original.leg_id
