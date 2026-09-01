# RKA App working instructions

RKA App is the installation and machine-integration layer for RKA Core. Keep
the product boundary strict.

## Ownership

RKA App may own process supervision, deployment manifests, installers,
diagnostics, upgrades, rollback, client configuration, and future native
packaging. It consumes released RKA Core artifacts through public CLI, REST,
and MCP contracts.

Do not copy Core source, import `rka.*`, open `rka.db`, or make RKA App the
authority for research data. Changes needed in Core belong in a separate Core
branch and pull request.

## Safety

- Treat an existing RKA installation as protected external state.
- Never use Core's stock Compose file for parallel tests.
- Never use the names `rka-server`, `rka-worker`, project `rka`, volume
  `rka_rka-data`, or host ports `9712`/`9713` in tests.
- Use unique labels and exact resource names for every Docker test.
- Never mount `~/.rka`, a live `rka-data` volume, or a user database.
- Do not modify real Codex, Claude Code, or Claude Desktop configuration in
  tests. Use disposable fixture paths.
- Never run broad cleanup commands such as `docker system prune`. Cleanup must
  validate the exact Foundation 0 label before deleting a resource.
- Snapshot protected live container identity, image, mounts, state, and health
  before and after integration tests; any unexplained change fails the test.

## Verification

Run `python -m unittest discover -s tests -v` for supervisor unit tests. For a
real integration run, use `scripts/isolation_smoke.py` with a clean Core source
checkout. The integration smoke must publish no host port, prove both Core
processes run, prove data survives container replacement, and read back the
protected live baseline afterward.

Images must consume an immutable Core digest in release configuration. Mutable
tags are acceptable only for uniquely named local test images that are deleted
by the same test run.
