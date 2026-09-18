"""Construction of the environment handed to the target process.

The runner environment carries credentials, most notably
`ACTIONS_RUNTIME_TOKEN` and `ACTIONS_RESULTS_URL`, which grant artifact write
access for the duration of the job. None of it reaches the benchmarked
process.

The environment is built from an allowlist rather than filtered from
`os.environ`, so a variable introduced by a future runner image is excluded by
default instead of included by default. Excluding ambient variables also
removes a source of measurement variance between runners.
"""

from collections.abc import Mapping

ALLOWED_KEYS = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "TEMP",
        "TMP",
        # Windows breaks subprocess creation without these two.
        "SYSTEMROOT",
        "COMSPEC",
    }
)


def build_target_env(
    *,
    source: Mapping[str, str],
    src_path: str,
    leg_path: str,
    report_path: str,
    cpu_count_override: int | None,
) -> dict[str, str]:
    """Build the environment the target subprocess runs under.

    Args:
        source: Environment to draw allowed values from, normally `os.environ`.
        src_path: Directory placed on `PYTHONPATH` so the target can import
            the workload package.
        leg_path: Path to the JSON leg description the target reads.
        report_path: Path the target writes its self-report to.
        cpu_count_override: Value for `PYTHON_CPU_COUNT`, or None to leave the
            interpreter's own reported count in place.

    Returns:
        A complete environment mapping. Nothing outside the allowlist and the
        benchmark variables appears in it.

    Raises:
        KeyError: If `PATH` is absent from the source environment.
    """
    env = {key: source[key] for key in ALLOWED_KEYS if key in source}
    env["PATH"] = source["PATH"]
    env["PYTHONPATH"] = src_path
    env["BENCH_LEG_PATH"] = leg_path
    env["BENCH_REPORT_PATH"] = report_path
    if cpu_count_override is not None:
        env["PYTHON_CPU_COUNT"] = str(cpu_count_override)
    return env
