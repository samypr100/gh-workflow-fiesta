"""Aggregation of repeated observations into reported scalars.

GitHub runners are shared machines. A single observation is not a benchmark,
so every leg runs several times and reports the median with the observed
spread, letting a reader see for themselves how noisy the measurement was.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, replace

from bench_contract.results import InnerReport, Scalars, ScalarStats, TimelinePoint


@dataclass(frozen=True)
class RepeatObservation:
    """One completed repeat of a leg.

    Attributes:
        report: The target's self-report for this repeat.
        peak_rss_bytes: Peak resident set size the sampler observed.
        timeline: Samples the sampler collected during this repeat.
    """

    report: InnerReport
    peak_rss_bytes: int
    timeline: list[TimelinePoint]

    def _replace_operations(self, operations: int | None) -> RepeatObservation:
        """Return a copy whose report carries a different operation count.

        Args:
            operations: Replacement operation count.

        Returns:
            The modified copy.
        """
        return replace(self, report=self.report.model_copy(update={"operations": operations}))


def _stats(values: Sequence[float]) -> ScalarStats:
    """Summarise a sequence of observations.

    Args:
        values: Observed values.

    Returns:
        The median and observed bounds.
    """
    return ScalarStats(
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
    )


def median_index(observations: Sequence[RepeatObservation]) -> int:
    """Find the repeat whose wall time is the median.

    The timeline and phase breakdown reported for a leg come from this repeat,
    so the trace a reader sees matches the scalars they see beside it.

    Args:
        observations: Completed repeats.

    Returns:
        Index of the representative repeat.

    Raises:
        ValueError: If no observations were supplied.
    """
    if len(observations) == 0:
        raise ValueError("need at least one observation")
    ordered = sorted(
        range(len(observations)), key=lambda index: observations[index].report.wall_time_s
    )
    return ordered[len(ordered) // 2]


def aggregate(observations: Sequence[RepeatObservation]) -> Scalars:
    """Combine repeats into the scalars reported for a leg.

    Args:
        observations: Completed repeats.

    Returns:
        Aggregate metrics.

    Raises:
        ValueError: If no observations were supplied.
    """
    if len(observations) == 0:
        raise ValueError("need at least one observation")

    walls = [item.report.wall_time_s for item in observations]
    users = [item.report.cpu_user_s for item in observations]
    systems = [item.report.cpu_sys_s for item in observations]
    peaks = [float(item.peak_rss_bytes) for item in observations]
    factors = [
        (item.report.cpu_user_s + item.report.cpu_sys_s) / item.report.wall_time_s
        for item in observations
    ]

    operation_counts = [item.report.operations for item in observations]
    throughput: ScalarStats | None = None
    if all(count is not None and count > 0 for count in operation_counts):
        throughput = _stats(
            [(item.report.operations or 0) / item.report.wall_time_s for item in observations]
        )

    return Scalars(
        wall_time_s=_stats(walls),
        cpu_user_s=_stats(users),
        cpu_sys_s=_stats(systems),
        parallelism_factor=_stats(factors),
        peak_rss_bytes=_stats(peaks),
        throughput_ops_s=throughput,
        repeats_completed=len(observations),
    )
