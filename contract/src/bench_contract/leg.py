"""Identity of a single benchmark matrix leg."""

import hashlib

from pydantic import BaseModel, ConfigDict, computed_field

from bench_contract.enums import ExecutionModel, OperatingSystem, Variant, WorkloadKind
from bench_contract.params import WorkloadParams

DIGEST_BYTES = 4


class LegKey(BaseModel):
    """Everything that uniquely identifies one benchmark execution.

    Attributes:
        os: Operating system the leg runs on.
        arch: Runner architecture, for example `x86_64` or `aarch64`.
        python_key: Full uv interpreter key, for example
            `cpython-3.14.7+freethreaded-linux-x86_64-gnu`.
        variant: Build variant, mirroring the uv key.
        workload: Nature of the work performed.
        execution_model: Concurrency strategy used.
        params: Tunable workload parameters.
        cpu_count_override: Value forced through `PYTHON_CPU_COUNT`, or None to
            leave the interpreter's own reported count in place.
    """

    model_config = ConfigDict(frozen=True)

    os: OperatingSystem
    arch: str
    python_key: str
    variant: Variant
    workload: WorkloadKind
    execution_model: ExecutionModel
    params: WorkloadParams
    cpu_count_override: int | None = None

    @computed_field
    @property
    def leg_id(self) -> str:
        """Stable, artifact-name-safe identifier derived from every field.

        Returns:
            A slug of the form `<os>-<execution_model>-<digest>`.
        """
        parts = (
            self.os.value,
            self.arch,
            self.python_key,
            self.variant.value,
            self.workload.value,
            self.execution_model.value,
            str(self.params.workers),
            str(self.params.iterations),
            str(self.params.repeats),
            str(self.cpu_count_override),
        )
        digest = hashlib.blake2b(
            "|".join(parts).encode("utf-8"), digest_size=DIGEST_BYTES
        ).hexdigest()
        return f"{self.os.value}-{self.execution_model.value}-{digest}"
