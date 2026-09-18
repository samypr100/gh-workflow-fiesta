"""Discovery of the interpreters a benchmark run may target.

The list is not maintained by hand. uv already knows every interpreter it can
install on every platform, and its `variant` field is exactly the GIL axis this
application compares, so the catalogue is derived from uv directly.
"""

import asyncio
import json
import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import structlog
from bench_contract.dispatch import RUNNER_IMAGES
from bench_contract.enums import OperatingSystem, Variant
from pydantic import BaseModel, ConfigDict, TypeAdapter

PROBE_TIMEOUT_S = 60.0
MINOR_VERSION_PATTERN = re.compile(r"^3\.(\d+)")
SUPPORTED_LIBC = frozenset({"gnu", "none", None})

log = structlog.get_logger(__name__)


class UvDownload(BaseModel):
    """One entry from `uv python list --output-format json`.

    Attributes:
        key: Full interpreter key.
        version: Full version string.
        os: Operating system name as uv reports it.
        arch: Architecture name as uv reports it.
        variant: Build variant, `default` or `freethreaded`.
        implementation: Interpreter implementation name.
        libc: C library name, or None where it does not apply.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    key: str
    version: str
    os: str
    arch: str
    variant: str
    implementation: str
    libc: str | None = None


@dataclass(frozen=True)
class RunnerTarget:
    """A GitHub runner image and the interpreter builds it can run.

    Attributes:
        os: Operating system the image provides.
        arch: Architecture the image provides.
        image: Runner label used in `runs-on`.
    """

    os: OperatingSystem
    arch: str
    image: str


RUNNER_TARGETS: tuple[RunnerTarget, ...] = (
    RunnerTarget(
        os=OperatingSystem.LINUX,
        arch="x86_64",
        image=RUNNER_IMAGES[OperatingSystem.LINUX],
    ),
    RunnerTarget(
        os=OperatingSystem.MACOS,
        arch="aarch64",
        image=RUNNER_IMAGES[OperatingSystem.MACOS],
    ),
    RunnerTarget(
        os=OperatingSystem.WINDOWS,
        arch="x86_64",
        image=RUNNER_IMAGES[OperatingSystem.WINDOWS],
    ),
)

_TARGETS_BY_PAIR = {(target.os.value, target.arch): target for target in RUNNER_TARGETS}


class InterpreterOption(BaseModel):
    """An interpreter the frontend may offer for selection.

    Attributes:
        python_key: Full uv key, passed through to the workflow unchanged.
        version: Full version string.
        python_minor: Minor version number, used for capability checks.
        os: Operating system this build runs on.
        arch: Architecture this build runs on.
        variant: Build variant.
        gil_enabled: Whether this build has a GIL, derived from the variant.
    """

    model_config = ConfigDict(frozen=True)

    python_key: str
    version: str
    python_minor: int
    os: OperatingSystem
    arch: str
    variant: Variant
    gil_enabled: bool


async def probe_uv(*, uv_executable: str) -> tuple[UvDownload, ...]:
    """Ask uv which interpreters it can install, for every platform.

    Args:
        uv_executable: Path to the uv binary.

    Returns:
        Every download uv reported.

    Raises:
        FileNotFoundError: If the uv binary does not exist.
        RuntimeError: If uv exited non-zero or produced unreadable output.
    """
    process = await asyncio.create_subprocess_exec(
        uv_executable,
        "python",
        "list",
        # Explicit, because UV_NO_MANAGED_PYTHON in the ambient environment
        # otherwise yields an empty list with exit status zero.
        "--managed-python",
        "--all-platforms",
        "--all-arches",
        "--only-downloads",
        "--output-format",
        "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    async with asyncio.timeout(PROBE_TIMEOUT_S):
        stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            f"uv python list exited with {process.returncode}: "
            f"{stderr.decode('utf-8', errors='replace').strip()}"
        )
    try:
        downloads = TypeAdapter(tuple[UvDownload, ...]).validate_json(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("uv python list produced unreadable output") from error

    log.info("interpreters.probed", extra={"count": len(downloads)})
    return downloads


def filter_options(downloads: Iterable[UvDownload]) -> tuple[InterpreterOption, ...]:
    """Reduce uv's catalogue to what a GitHub runner can actually execute.

    Args:
        downloads: Entries reported by uv.

    Returns:
        The selectable options, in the order they were supplied.
    """
    options: list[InterpreterOption] = []
    for item in downloads:
        if item.implementation != "cpython":
            continue
        if item.libc not in SUPPORTED_LIBC:
            continue
        target = _TARGETS_BY_PAIR.get((item.os, item.arch))
        if target is None:
            continue
        match = MINOR_VERSION_PATTERN.match(item.version)
        if match is None:
            continue
        variant = Variant(item.variant)
        options.append(
            InterpreterOption(
                python_key=item.key,
                version=item.version,
                python_minor=int(match.group(1)),
                os=target.os,
                arch=target.arch,
                variant=variant,
                gil_enabled=variant is Variant.DEFAULT,
            )
        )
    return tuple(options)


@dataclass
class InterpreterCache:
    """Caches the interpreter list for a bounded period.

    uv's catalogue changes on the order of weeks, and probing spawns a
    subprocess, so a short in-process cache avoids doing that per request.
    This is a performance detail, not state: losing it costs one subprocess.

    Attributes:
        uv_executable: Path to the uv binary.
        ttl_seconds: How long a probe result stays usable.
    """

    uv_executable: str
    ttl_seconds: int
    _options: tuple[InterpreterOption, ...] = field(default=(), init=False)
    _fetched_at: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def get(self, *, now: float | None = None) -> tuple[InterpreterOption, ...]:
        """Return the selectable interpreters, probing if the cache is cold.

        Args:
            now: Current monotonic time, for testing.

        Returns:
            The selectable options.
        """
        current = time.monotonic() if now is None else now
        async with self._lock:
            is_fresh = len(self._options) > 0 and current - self._fetched_at < self.ttl_seconds
            if is_fresh:
                return self._options
            downloads = await probe_uv(uv_executable=self.uv_executable)
            self._options = filter_options(downloads)
            self._fetched_at = current
            return self._options


def options_for_runner(
    options: Sequence[InterpreterOption], target: RunnerTarget
) -> tuple[InterpreterOption, ...]:
    """Select the options that run on a given runner image.

    Args:
        options: Available options.
        target: Runner image to filter for.

    Returns:
        The matching options.
    """
    return tuple(
        option for option in options if option.os is target.os and option.arch == target.arch
    )
