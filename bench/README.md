# bench

The harness that executes one benchmark leg inside GitHub Actions.

`workloads/` and `target/` are pure standard library so they run on any
interpreter. `harness/` runs only on the pinned 3.14 interpreter and holds
every third-party dependency.
