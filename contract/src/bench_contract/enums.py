"""Closed sets used throughout the benchmark contract."""

import enum


class OperatingSystem(enum.StrEnum):
    """Operating system a benchmark leg runs on."""

    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"


class Variant(enum.StrEnum):
    """CPython build variant, mirroring the `variant` field emitted by uv."""

    DEFAULT = "default"
    FREETHREADED = "freethreaded"


class WorkloadKind(enum.StrEnum):
    """Nature of the work a benchmark performs."""

    CPU_BOUND = "cpu_bound"
    IO_BOUND = "io_bound"
    MIXED = "mixed"


class ExecutionModel(enum.StrEnum):
    """Concurrency strategy used to execute a workload."""

    SEQUENTIAL = "sequential"
    THREADING = "threading"
    ASYNCIO = "asyncio"
    MULTIPROCESSING = "multiprocessing"
    SUBINTERPRETERS = "subinterpreters"


class RunStatus(enum.StrEnum):
    """Terminal state of a single benchmark leg."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class CpuCountSource(enum.StrEnum):
    """Whether the effective CPU count was observed or forced."""

    REPORTED = "reported"
    OVERRIDE = "override"
