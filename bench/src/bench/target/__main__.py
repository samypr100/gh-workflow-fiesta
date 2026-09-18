"""Entrypoint executed under the target interpreter.

Standard library only, and deliberately so: this runs on whichever interpreter
the user selected, including free-threaded builds and versions for which no
`psutil` wheel exists. It reads its leg from `BENCH_LEG_PATH` and writes an
`InnerReport`-shaped JSON document to `BENCH_REPORT_PATH`.

Run as `python -m bench.target` with `PYTHONPATH` pointing at `bench/src`.
"""

import json
import os
import platform
import sys
import time

from bench.target.models import EXECUTION_MODELS

GIL_INTROSPECTION_MINIMUM = (3, 13)


def gil_enabled() -> bool:
    """Report whether the GIL is active in this interpreter.

    Returns:
        True when the GIL is enabled. Interpreters older than 3.13 have no
        free-threaded build, so the answer there is unconditionally True.
    """
    if sys.version_info < GIL_INTROSPECTION_MINIMUM:
        return True
    return sys._is_gil_enabled()


def main() -> int:
    """Run the configured workload and write the self-report.

    Returns:
        A process exit status.
    """
    leg_path = os.environ["BENCH_LEG_PATH"]
    report_path = os.environ["BENCH_REPORT_PATH"]

    setup_start = time.perf_counter()
    with open(leg_path, encoding="utf-8") as handle:
        leg = json.load(handle)

    model_name = leg["execution_model"]
    runner = EXECUTION_MODELS.get(model_name)
    if runner is None:
        print(f"unknown execution model: {model_name}", file=sys.stderr)
        return 2

    workers = int(leg["workers"])
    iterations = int(leg["iterations"])
    setup_duration = time.perf_counter() - setup_start

    times_before = os.times()
    work_start = time.perf_counter()
    operations = runner(workers, iterations)
    wall_time = time.perf_counter() - work_start
    times_after = os.times()

    report = {
        "phases": [
            {"name": "setup", "duration_s": setup_duration},
            {"name": "work", "duration_s": wall_time},
        ],
        "operations": operations,
        "wall_time_s": wall_time,
        "cpu_user_s": times_after.user - times_before.user,
        "cpu_sys_s": times_after.system - times_before.system,
        "gil_enabled": gil_enabled(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "cpu_count_effective": os.cpu_count() or 1,
    }
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
