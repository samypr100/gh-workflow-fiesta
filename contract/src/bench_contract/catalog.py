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
        source_path: Repository path of the code this entry executes, so a
            reader can check the snippet below against what actually ran.
        source_code: The kernel and execution strategy, as displayed in the
            interface. Kept verbatim from the modules named in `source_path`;
            `KERNEL_SOURCE` holds the shared part.
    """

    model_config = ConfigDict(frozen=True)

    workload: WorkloadKind
    execution_model: ExecutionModel
    minimum_python_minor: int
    title: str
    explainer: str
    expectation: str
    source_path: str
    source_code: str


# The workload kernel every execution model drives. Shown above each strategy
# so a reader can see that the work itself is identical and only the way it is
# scheduled changes.
KERNEL_SOURCE = '''# bench/src/bench/workloads/cpu.py
MODULUS = 1_000_003
MULTIPLIER = 31


def cpu_chunk(iterations: int) -> int:
    """Run a fixed amount of interpreted arithmetic."""
    total = 0
    for index in range(iterations):
        total = (total * MULTIPLIER + index * index) % MODULUS
    return total
'''

MODELS_PATH = "bench/src/bench/target/models.py"

SEQUENTIAL_SOURCE = f"""{KERNEL_SOURCE}

# {MODELS_PATH}
def run_sequential(workers: int, iterations: int) -> int:
    for _ in range(workers):
        cpu_chunk(iterations)
    return workers * iterations
"""

THREADING_SOURCE = f"""{KERNEL_SOURCE}

# {MODELS_PATH}
import threading


def run_threading(workers: int, iterations: int) -> int:
    threads = [
        threading.Thread(target=cpu_chunk, args=(iterations,))
        for _ in range(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return workers * iterations
"""

ASYNCIO_SOURCE = f"""{KERNEL_SOURCE}

# {MODELS_PATH}
import asyncio


def run_asyncio(workers: int, iterations: int) -> int:
    async def chunk() -> None:
        cpu_chunk(iterations)

    async def main() -> None:
        async with asyncio.TaskGroup() as group:
            for _ in range(workers):
                group.create_task(chunk())

    # asyncio.Runner is 3.11+, so no backport is needed here.
    with asyncio.Runner() as runner:
        runner.run(main())
    return workers * iterations
"""

SUBINTERPRETERS_SOURCE = f"""{KERNEL_SOURCE}

# {MODELS_PATH}  (requires Python 3.14+)
def run_subinterpreters(workers: int, iterations: int) -> int:
    from concurrent.futures import InterpreterPoolExecutor

    with InterpreterPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(cpu_chunk, iterations) for _ in range(workers)]
        for future in futures:
            future.result()
    return workers * iterations
"""


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
        source_path=MODELS_PATH,
        source_code=SEQUENTIAL_SOURCE,
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
        source_path=MODELS_PATH,
        source_code=THREADING_SOURCE,
    ),
    CatalogEntry(
        workload=WorkloadKind.CPU_BOUND,
        execution_model=ExecutionModel.ASYNCIO,
        minimum_python_minor=12,
        title="CPU-bound, asyncio",
        explainer=(
            "Schedules the same arithmetic as coroutines on one event loop. asyncio "
            "interleaves tasks at await points, and a chunk of pure arithmetic never "
            "awaits, so the loop runs them one after another."
        ),
        expectation=(
            "Parallelism factor stays near 1.0 and wall time matches the sequential "
            "baseline, whatever the worker count. This is the difference between "
            "concurrency and parallelism: asyncio gives you the former, and CPU-bound "
            "work needs the latter. Compare it against threads on a free-threaded "
            "build to see the gap."
        ),
        source_path=MODELS_PATH,
        source_code=ASYNCIO_SOURCE,
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
        source_path=MODELS_PATH,
        source_code=SUBINTERPRETERS_SOURCE,
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
