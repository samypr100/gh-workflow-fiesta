"""Names and shapes shared between the dispatcher and the workflow."""

import enum
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from bench_contract.enums import OperatingSystem
from bench_contract.leg import LegKey

WORKFLOW_FILENAME = "benchmark.yml"
RESULT_FILENAME = "result.json"
ARTIFACT_PREFIX = "result-"
DEFAULT_TIMEOUT_SECONDS = 300
MAX_MATRIX_JOBS = 256

RUNNER_IMAGES: Mapping[OperatingSystem, str] = {
    OperatingSystem.LINUX: "ubuntu-latest",
    OperatingSystem.MACOS: "macos-latest",
    OperatingSystem.WINDOWS: "windows-latest",
}


class DispatchInput(enum.StrEnum):
    """Top-level `workflow_dispatch` input names.

    GitHub allows at most 25 top-level inputs and 65,535 characters in total.
    """

    MATRIX = "matrix"
    USER_KEY = "user_key"
    SUBMISSION_ID = "submission_id"
    TIMEOUT_SECONDS = "timeout_seconds"


def artifact_name(leg_id: str) -> str:
    """Build the artifact name a leg uploads its result under.

    Args:
        leg_id: Identifier of the leg.

    Returns:
        The artifact name.
    """
    return f"{ARTIFACT_PREFIX}{leg_id}"


class MatrixInclude(BaseModel):
    """One entry of the GitHub Actions matrix `include` list.

    Attributes:
        leg_id: Identifier used for the artifact name and job name.
        runs_on: Runner image label.
        python_key: uv interpreter key the job installs.
        leg_json: The full leg, serialised, for the harness to parse.
    """

    model_config = ConfigDict(frozen=True)

    leg_id: str
    runs_on: str
    python_key: str
    leg_json: str


class DispatchMatrix(BaseModel):
    """The object passed to `fromJSON` as the job strategy matrix.

    Attributes:
        include: One entry per benchmark leg.
    """

    model_config = ConfigDict(frozen=True)

    include: list[MatrixInclude]


def build_matrix(legs: Sequence[LegKey]) -> DispatchMatrix:
    """Convert legs into the flat matrix GitHub Actions accepts.

    Args:
        legs: Legs to execute.

    Returns:
        The matrix object.
    """
    return DispatchMatrix(
        include=[
            MatrixInclude(
                leg_id=leg.leg_id,
                runs_on=RUNNER_IMAGES[leg.os],
                python_key=leg.python_key,
                leg_json=leg.model_dump_json(),
            )
            for leg in legs
        ]
    )
