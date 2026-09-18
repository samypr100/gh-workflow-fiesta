"""Tests for workload parameter validation."""

import pytest
from bench_contract.params import WorkloadParams
from pydantic import ValidationError


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
    field_name = "workers"
    with pytest.raises(ValidationError):
        # Assigning through setattr (rather than attribute syntax) keeps this
        # a runtime-only check; frozen fields are statically read-only, so
        # `params.workers = 8` would be flagged by mypy as invalid on its own.
        setattr(params, field_name, 8)
