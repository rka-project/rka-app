# RKA App

Installation, lifecycle supervision, and deployment adapters for
[RKA Core](https://github.com/rka-project/rka-core).

> **Foundation 0 status:** experimental and not yet an end-user release.

RKA App is the machine-integration layer around RKA Core. It consumes released
Core artifacts through their public CLI, REST, and MCP contracts; it does not
copy Core source or import Core internals.

## Repository boundary

RKA Core owns durable research records, provenance, retrieval, integrity,
migrations, backup, REST, MCP, and its maintenance dashboard. RKA App owns:

- lifecycle supervision and stable launchers;
- local and user-owned cloud deployment adapters;
- installation diagnostics, upgrades, and rollback;
- safe Codex and Claude configuration;
- future native packaging, if it is still justified after the headless path.

Foundation 0 contains only the shared runtime substrate: a minimal PID 1
supervisor, a derived container image, and an isolation smoke test. Hugging Face
templates, client configuration, automatic updates, and a desktop UI are out of
scope for this milestone.

## Container contract

The derived image requires an immutable Core image reference at build time:

```bash
docker build \
  --build-arg RKA_CORE_IMAGE='ghcr.io/rka-project/rka-core@sha256:<digest>' \
  -t rka-app:foundation0 .
```

The container exposes one HTTP port (default `7860`) and supervises both Core
processes:

```text
rka-app supervisor (PID 1)
├── rka serve --host 0.0.0.0 --port 7860
└── rka worker
```

The worker starts only after `/api/health` succeeds. If either child exits
unexpectedly, the supervisor terminates the other and exits non-zero. SIGTERM
and SIGINT produce a bounded, ordered shutdown.

Configuration:

| Variable | Default | Purpose |
|---|---:|---|
| `RKA_HOST` | `0.0.0.0` | Core server bind address inside the container |
| `RKA_PORT` | `7860` | Single externally exposed HTTP port |
| `RKA_APP_WORKER_ENABLED` | `true` | Start the background worker |
| `RKA_APP_STARTUP_TIMEOUT` | `120` | Seconds allowed for Core readiness |
| `RKA_APP_SHUTDOWN_TIMEOUT` | `20` | Seconds allowed per child during shutdown |
| `RKA_APP_HEALTH_INTERVAL` | `0.25` | Readiness polling interval in seconds |

## Development

Run the dependency-free unit tests:

```bash
python -m unittest discover -s tests -v
```

Run the real Core integration smoke in a disposable Docker namespace:

```bash
python scripts/isolation_smoke.py \
  --core-source /absolute/path/to/rka-core
```

The smoke test does **not** publish a host port. It creates exact, uniquely
labelled test images, containers, network, and volume; verifies project data
survives a container replacement; then removes only those resources. It
snapshots any protected live containers and the local `9712` health endpoint
before and after the run and fails if they change.

Never use RKA Core's stock Compose file for a parallel Foundation 0 test: its
fixed container names, port, and volume can collide with a live installation.

## Release dependency

RKA Core does not yet publish the required GHCR artifact. Until its tagged
multi-architecture image workflow is reviewed and released, Foundation 0 tests
build a uniquely tagged Core image from a clean local Core checkout. RKA App
will pin the first released image by digest; it will never default to `latest`.
