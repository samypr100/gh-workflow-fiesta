"""Tunable parameters shared by every workload."""

from pydantic import BaseModel, ConfigDict, Field

MAX_WORKERS = 64
MAX_ITERATIONS = 10_000_000
MAX_REPEATS = 10
DEFAULT_REPEATS = 3


class WorkloadParams(BaseModel):
    """Parameters a user tunes for a workload.

    Attributes:
        workers: Number of concurrent units the execution model should create.
        iterations: Units of work each worker performs.
        repeats: How many times the whole measurement is repeated.
    """

    model_config = ConfigDict(frozen=True)

    workers: int = Field(ge=1, le=MAX_WORKERS)
    iterations: int = Field(ge=1, le=MAX_ITERATIONS)
    repeats: int = Field(default=DEFAULT_REPEATS, ge=1, le=MAX_REPEATS)
