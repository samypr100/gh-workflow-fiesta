# gh-workflow-fiesta

Educational explorer for Python concurrency behavior across interpreter
versions, GIL modes, operating systems, and execution models.

## Layout

| Path | Purpose |
|---|---|
| `contract/` | Shared pydantic contract: models, dispatch names, workload catalog |
| `bench/` | CI harness and pure-stdlib workloads |
| `proxy_be/` | Stateless FastAPI backend |
| `proxy_fe/` | Vue frontend |
| `.github/workflows/benchmark.yml` | The workflow legs execute in |

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy contract bench proxy_be
```

Regenerate the golden fixtures after changing any contract model:

```bash
uv run python scripts/generate_fixtures.py
```

Design and plans live under `docs/superpowers/`.
