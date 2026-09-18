"""Tests for the workload catalog."""

import pytest

from bench_contract.catalog import (
    CATALOG,
    find_entry,
    python_minor_from_key,
    supports_version,
)
from bench_contract.enums import ExecutionModel, WorkloadKind


def test_catalog_has_three_phase_one_entries() -> None:
    assert len(CATALOG) == 3


def test_every_entry_is_uniquely_keyed() -> None:
    keys = {(entry.workload, entry.execution_model) for entry in CATALOG}
    assert len(keys) == len(CATALOG)


def test_every_entry_carries_teaching_copy() -> None:
    for entry in CATALOG:
        assert entry.title != ""
        assert entry.explainer != ""
        assert entry.expectation != ""


def test_find_entry_returns_the_match() -> None:
    entry = find_entry(WorkloadKind.CPU_BOUND, ExecutionModel.THREADING)
    assert entry is not None
    assert entry.execution_model is ExecutionModel.THREADING


def test_find_entry_returns_none_for_an_unshipped_combination() -> None:
    assert find_entry(WorkloadKind.IO_BOUND, ExecutionModel.ASYNCIO) is None


@pytest.mark.parametrize(
    ("python_key", "expected"),
    [
        ("cpython-3.14.7-linux-x86_64-gnu", 14),
        ("cpython-3.13.15+freethreaded-macos-aarch64-none", 13),
        ("cpython-3.15.0rc2-windows-x86_64-none", 15),
    ],
)
def test_python_minor_from_key(python_key: str, expected: int) -> None:
    assert python_minor_from_key(python_key) == expected


def test_subinterpreters_require_three_fourteen() -> None:
    entry = find_entry(WorkloadKind.CPU_BOUND, ExecutionModel.SUBINTERPRETERS)
    assert entry is not None
    assert supports_version(entry, 13) is False
    assert supports_version(entry, 14) is True


def test_threading_is_supported_everywhere() -> None:
    entry = find_entry(WorkloadKind.CPU_BOUND, ExecutionModel.THREADING)
    assert entry is not None
    assert supports_version(entry, 12) is True
