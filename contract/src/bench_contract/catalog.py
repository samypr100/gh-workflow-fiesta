"""The curated catalog of workloads and execution models."""

import re

from pydantic import BaseModel, ConfigDict

from bench_contract.enums import ExecutionModel, WorkloadKind

MINOR_VERSION_PATTERN = re.compile(r"^[a-z]+-3\.(\d+)")


class CatalogEntry(BaseModel):
    """One selectable workload and execution model combination.

    Attributes:
        workload: Nature of the work performed.
        execution_model: Concurrency strategy used.
        minimum_python_minor: Lowest Python 3.x minor version that supports this
            combination.
        title: Short label shown in the interface.
        explainer: What this combination does, for a reader who does not already
            know the concurrency model.
        expectation: What the measurement should look like, so a surprising result
            is recognisable as surprising.
    """

    model_config = ConfigDict(frozen=True)

    workload: WorkloadKind
    execution_model: ExecutionModel
    minimum_python_minor: int
    title: str
    explainer: str
    expectation: str


CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        workload=WorkloadKind.CPU_BOUND,
        execution_model=ExecutionModel.SEQUENTIAL,
        minimum_python_minor=12,
        title="CPU-bound, sequential",
        explainer=(
            "Runs the same arithmetic workload one chunk after another in a single "
            "thread. This is the baseline every other execution model is measured "
            "against."
        ),
        expectation=(
            "Parallelism factor sits near 1.0 because only one core is ever busy. "
            "Wall time and CPU time are nearly equal."
        ),
    ),
    CatalogEntry(
        workload=WorkloadKind.CPU_BOUND,
        execution_model=ExecutionModel.THREADING,
        minimum_python_minor=12,
        title="CPU-bound, threads",
        explainer=(
            "Splits the same arithmetic workload across worker threads. Threads share "
            "one interpreter, so whether they run at the same time depends entirely on "
            "whether the GIL is enabled."
        ),
        expectation=(
            "With the GIL enabled the parallelism factor stays near 1.0 no matter how "
            "many workers you add. On a free-threaded build it should climb toward the "
            "worker count. This contrast is the clearest demonstration of what the GIL "
            "actually costs."
        ),
    ),
    CatalogEntry(
        workload=WorkloadKind.CPU_BOUND,
        execution_model=ExecutionModel.SUBINTERPRETERS,
        minimum_python_minor=14,
        title="CPU-bound, subinterpreters",
        explainer=(
            "Splits the workload across independent interpreters inside one process "
            "using concurrent.interpreters. Each interpreter owns its own state, so "
            "they do not contend for a shared GIL."
        ),
        expectation=(
            "Parallelism factor climbs toward the worker count even on a build with the "
            "GIL enabled, because each interpreter has its own. Startup cost is higher "
            "than threads, so short runs may show less benefit."
        ),
    ),
)


def find_entry(workload: WorkloadKind, execution_model: ExecutionModel) -> CatalogEntry | None:
    """Look up a catalog entry.

    Args:
        workload: Nature of the work.
        execution_model: Concurrency strategy.

    Returns:
        The matching entry, or None if the combination is not shipped.
    """
    for entry in CATALOG:
        if entry.workload is workload and entry.execution_model is execution_model:
            return entry
    return None


def supports_version(entry: CatalogEntry, python_minor: int) -> bool:
    """Report whether an entry can run on a given Python minor version.

    Args:
        entry: Catalog entry to check.
        python_minor: Minor version number, for example 14 for Python 3.14.

    Returns:
        True when the combination is available on that version.
    """
    return python_minor >= entry.minimum_python_minor


def python_minor_from_key(python_key: str) -> int:
    """Extract the Python minor version from a uv interpreter key.

    Args:
        python_key: A uv key, for example `cpython-3.14.7-linux-x86_64-gnu`.

    Returns:
        The minor version number.

    Raises:
        ValueError: If the key does not carry a recognisable 3.x version.
    """
    match = MINOR_VERSION_PATTERN.match(python_key)
    if match is None:
        raise ValueError(f"unrecognised interpreter key: {python_key}")
    return int(match.group(1))
