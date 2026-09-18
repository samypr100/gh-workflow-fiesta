"""Tests for the golden fixtures."""

import json
import pathlib

from bench_contract.enums import RunStatus
from bench_contract.fixtures import sample_results
from bench_contract.results import RunResult

FIXTURE_DIR = pathlib.Path(__file__).parent.parent / "fixtures"


def test_sample_results_cover_every_status() -> None:
    statuses = {result.status for result in sample_results()}
    assert statuses == set(RunStatus)


def test_sample_results_contrast_gil_modes() -> None:
    gil_states = {
        result.environment.gil_enabled
        for result in sample_results()
        if result.environment is not None
    }
    assert gil_states == {True, False}


def test_committed_fixtures_match_the_models() -> None:
    files = sorted(FIXTURE_DIR.glob("*.json"))
    assert len(files) == len(sample_results())
    for path in files:
        RunResult.model_validate_json(path.read_text(encoding="utf-8"))


def test_committed_fixtures_are_current() -> None:
    for result in sample_results():
        path = FIXTURE_DIR / f"{result.leg.leg_id}.json"
        assert path.exists(), f"missing fixture for {result.leg.leg_id}"
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == json.loads(result.model_dump_json())
