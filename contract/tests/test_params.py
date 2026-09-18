"""Tests for workload parameter validation."""

import pytest
from pydantic import ValidationError

from bench_contract.params import WorkloadParams


def test_defaults_to_three_repeats() -> None:
    params = WorkloadParams(workers=4, iterations=1000)
    assert params.repeats == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workers", 0),
        ("workers", 65),
        ("iterations", 0),
        ("repeats", 0),
        ("repeats", 11),
    ],
)
def test_rejects_out_of_range_values(field: str, value: int) -> None:
    kwargs = {"workers": 4, "iterations": 1000} | {field: value}
    with pytest.raises(ValidationError):
        WorkloadParams(**kwargs)


def test_is_frozen() -> None:
    params = WorkloadParams(workers=4, iterations=1000)
    with pytest.raises(ValidationError):
        params.workers = 8
