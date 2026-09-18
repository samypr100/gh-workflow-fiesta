"""Deduplication and rate limiting, decided from GitHub's own run list.

The backend stores nothing. Whether a user already has a run in flight, and
how many they have started recently, are both answered by the system that
bills the minutes. This module is the policy, expressed as a pure function so
every boundary case is testable without a network.
"""

import datetime
import enum
from collections.abc import Sequence
from dataclasses import dataclass

from proxy_be.github import WorkflowRun


class AdmissionVerdict(enum.StrEnum):
    """Outcome of an admission check."""

    ADMITTED = "admitted"
    DUPLICATE = "duplicate"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class AdmissionDecision:
    """Why a submission was admitted or refused.

    Attributes:
        verdict: The outcome.
        active_run_id: Identifier of the run already in flight, when the
            verdict is a duplicate.
        retry_after_seconds: Seconds until the quota frees up, when the verdict
            is a rate limit.
    """

    verdict: AdmissionVerdict
    active_run_id: int | None = None
    retry_after_seconds: int = 0


def check_admission(
    *,
    runs: Sequence[WorkflowRun],
    user_key: str,
    now: datetime.datetime,
    window_seconds: int,
    max_runs: int,
) -> AdmissionDecision:
    """Decide whether a user may start another benchmark run.

    Args:
        runs: Recent runs, as reported by GitHub.
        user_key: Derived key of the requesting user.
        now: Current time.
        window_seconds: Width of the rate-limit window.
        max_runs: Runs permitted within that window.

    Returns:
        The decision.
    """
    owned = [item for item in runs if item.user_key == user_key]

    for item in owned:
        if item.is_active is True:
            return AdmissionDecision(verdict=AdmissionVerdict.DUPLICATE, active_run_id=item.id)

    window_start = now - datetime.timedelta(seconds=window_seconds)
    in_window = [item for item in owned if item.created_at > window_start]
    if len(in_window) < max_runs:
        return AdmissionDecision(verdict=AdmissionVerdict.ADMITTED)

    oldest = min(item.created_at for item in in_window)
    elapsed = (now - oldest).total_seconds()
    return AdmissionDecision(
        verdict=AdmissionVerdict.RATE_LIMITED,
        retry_after_seconds=max(1, int(window_seconds - elapsed)),
    )
