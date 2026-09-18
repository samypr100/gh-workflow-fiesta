"""Strategies for executing a workload kernel concurrently.

Standard library only. Imported by the target interpreter, which has no
third-party packages installed.
"""

import sys
import threading
from collections.abc import Callable, Mapping

from bench.workloads.cpu import OPERATIONS_PER_ITERATION, cpu_chunk

SUBINTERPRETER_MINIMUM = (3, 14)


def run_sequential(workers: int, iterations: int) -> int:
    """Run every chunk one after another on the calling thread.

    Args:
        workers: Number of chunks to run.
        iterations: Iterations per chunk.

    Returns:
        Total operations performed.
    """
    for _ in range(workers):
        cpu_chunk(iterations)
    return workers * iterations * OPERATIONS_PER_ITERATION


def run_threading(workers: int, iterations: int) -> int:
    """Run each chunk on its own thread within one interpreter.

    Args:
        workers: Number of threads to start.
        iterations: Iterations per thread.

    Returns:
        Total operations performed.
    """
    threads = [threading.Thread(target=cpu_chunk, args=(iterations,)) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return workers * iterations * OPERATIONS_PER_ITERATION


def run_subinterpreters(workers: int, iterations: int) -> int:
    """Run each chunk in its own interpreter within one process.

    Args:
        workers: Number of interpreters to use.
        iterations: Iterations per interpreter.

    Returns:
        Total operations performed.

    Raises:
        RuntimeError: If the running interpreter predates 3.14, where
            `concurrent.futures.InterpreterPoolExecutor` was introduced.
    """
    if sys.version_info < SUBINTERPRETER_MINIMUM:
        raise RuntimeError(
            "subinterpreter execution requires Python 3.14 or newer; "
            f"this interpreter is {sys.version.split()[0]}"
        )
    # Imported here rather than at module level because the module does not
    # exist before 3.14 and this file must stay importable on 3.12 and 3.13.
    from concurrent.futures import InterpreterPoolExecutor

    with InterpreterPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(cpu_chunk, iterations) for _ in range(workers)]
        for future in futures:
            future.result()
    return workers * iterations * OPERATIONS_PER_ITERATION


EXECUTION_MODELS: Mapping[str, Callable[[int, int], int]] = {
    "sequential": run_sequential,
    "threading": run_threading,
    "subinterpreters": run_subinterpreters,
}
