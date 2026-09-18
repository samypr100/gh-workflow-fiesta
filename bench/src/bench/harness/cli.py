"""Command line entrypoint invoked by the benchmark workflow.

A failed benchmark is a result, not an error. This command writes a
`RunResult` and exits zero in every case except a malformed invocation, so the
workflow always has an artifact to upload and the frontend can show the user
what happened.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path

import structlog
from bench_contract.enums import RunStatus
from bench_contract.leg import LegKey
from bench_contract.results import LegError, RunResult

from bench.harness.interpreter import InterpreterInstallFailedError, install_interpreter
from bench.harness.runner import run_leg

log = structlog.get_logger(__name__)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: Argument vector, or None to read from the process.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Run one benchmark leg.")
    parser.add_argument("--leg-json", required=True, help="Serialised LegKey.")
    parser.add_argument("--output", required=True, help="Path to write the result to.")
    parser.add_argument("--src-path", required=True, help="Directory for PYTHONPATH.")
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument(
        "--python-executable",
        default=None,
        help="Skip uv installation and use this interpreter instead.",
    )
    parser.add_argument("--uv-executable", default="uv")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one leg and write its result.

    Args:
        argv: Argument vector, or None to read from the process.

    Returns:
        Zero unless the invocation itself was malformed.
    """
    args = _parse_args(argv)
    leg = LegKey.model_validate_json(args.leg_json)
    output = Path(args.output)

    if args.python_executable is not None:
        executable = args.python_executable
    else:
        try:
            executable = install_interpreter(leg.python_key, uv_executable=args.uv_executable)
        except InterpreterInstallFailedError as error:
            log.error(
                "leg.interpreter_unavailable",
                extra={"leg_id": leg.leg_id, "python_key": leg.python_key},
                exc_info=error,
            )
            failure = RunResult(
                leg=leg,
                status=RunStatus.ERROR,
                environment=None,
                scalars=None,
                timeline=[],
                phases=[],
                error=LegError(kind="InterpreterInstallFailed", message=str(error)),
            )
            output.write_text(failure.model_dump_json(indent=2), encoding="utf-8")
            return 0

    result = run_leg(
        leg,
        src_path=args.src_path,
        python_executable=executable,
        timeout_seconds=args.timeout_seconds,
    )
    output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    log.info(
        "leg.completed",
        extra={"leg_id": leg.leg_id, "status": result.status.value},
    )
    return 0
