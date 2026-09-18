"""Write the golden fixtures to disk.

Run with `uv run python scripts/generate_fixtures.py` after changing any model
or fixture builder, then commit the result.
"""

import pathlib

from bench_contract.fixtures import sample_results

FIXTURE_DIR = pathlib.Path(__file__).parent.parent / "contract" / "fixtures"


def main() -> None:
    """Regenerate every fixture file."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in FIXTURE_DIR.glob("*.json"):
        stale.unlink()
    for result in sample_results():
        path = FIXTURE_DIR / f"{result.leg.leg_id}.json"
        path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
