"""Sampling of a target process tree from outside.

Runs on the pinned harness interpreter, where `psutil` is available. Sampling
from outside keeps measurement overhead out of the process being measured, and
means the target needs no third-party packages at all.
"""

import threading
import time
from dataclasses import dataclass, field

import psutil
import structlog
from bench_contract.results import TimelinePoint

SAMPLE_INTERVAL_S = 0.1

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SampleSet:
    """Everything the sampler observed during one target execution.

    Attributes:
        points: Samples in the order they were taken.
        peak_rss_bytes: Largest resident set size seen across the tree.
    """

    points: list[TimelinePoint]
    peak_rss_bytes: int


@dataclass
class Sampler:
    """Polls a process tree on a background thread.

    Attributes:
        pid: Process identifier of the target.
    """

    pid: int
    _points: list[TimelinePoint] = field(default_factory=list, init=False)
    _peak_rss: int = field(default=0, init=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def start(self) -> None:
        """Begin sampling on a background thread."""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> SampleSet:
        """Stop sampling and return what was collected.

        Returns:
            The collected samples and observed peak resident set size.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=SAMPLE_INTERVAL_S * 10)
        return SampleSet(points=list(self._points), peak_rss_bytes=self._peak_rss)

    def _loop(self) -> None:
        """Sample until the target exits or `stop` is called."""
        try:
            process = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            log.debug("sampler.target_already_gone", extra={"pid": self.pid})
            return

        started = time.perf_counter()
        process.cpu_percent()
        while not self._stop.is_set():
            time.sleep(SAMPLE_INTERVAL_S)
            try:
                self._sample(process, started)
            except psutil.NoSuchProcess, psutil.AccessDenied:
                log.debug("sampler.target_exited", extra={"pid": self.pid})
                return

    def _sample(self, process: psutil.Process, started: float) -> None:
        """Take one sample of the process tree.

        Args:
            process: Target process handle.
            started: Reference time the timeline is relative to.

        Raises:
            psutil.NoSuchProcess: If the target has exited.
            psutil.AccessDenied: If the target can no longer be inspected.
        """
        members = [process, *process.children(recursive=True)]
        cpu_percent = 0.0
        num_threads = 0
        rss = 0
        for member in members:
            with member.oneshot():
                cpu_percent += member.cpu_percent()
                num_threads += member.num_threads()
                rss += member.memory_info().rss
        self._peak_rss = max(self._peak_rss, rss)
        self._points.append(
            TimelinePoint(
                t_s=round(time.perf_counter() - started, 4),
                cpu_percent=round(cpu_percent, 2),
                num_threads=num_threads,
                rss_bytes=rss,
            )
        )
