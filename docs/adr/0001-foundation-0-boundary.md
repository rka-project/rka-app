# ADR 0001: Foundation 0 consumes RKA Core as an external product

- **Status:** Accepted
- **Date:** 2026-09-01

## Context

RKA needs a lower-friction installation and a user-owned cloud trial path, but
RKA Core is the authority for durable research records and should not absorb
host integration, deployment-provider behavior, or AI-client configuration.
The first shared prerequisite is a reliable single-container runtime that can
serve local installers and later Hugging Face templates.

The developer machine may already run a production-like RKA instance on port
9712 with irreplaceable local data. Distribution tests must therefore be
structurally incapable of reusing its names, ports, or storage.

## Decision

1. RKA App consumes a released RKA Core image through the public `rka serve`,
   `rka worker`, REST health, and project APIs. It does not import Core Python
   modules, copy Core source, or open Core's SQLite database.
2. Core publishes its own base image from a tagged Core commit. RKA App pins
   that image by digest and adds only the deployment supervisor and adapters.
3. The Foundation 0 supervisor is PID 1. It starts the API, waits for public
   readiness, starts the worker, propagates child failure, and performs bounded
   ordered shutdown.
4. Integration tests use a unique run token for every image, container,
   network, volume, and ownership label. They publish no host port.
5. Tests snapshot protected live container identity, image, state, mounts, and
   the 9712 health response before and after every run, including failure
   paths. Cleanup validates exact ownership labels before deletion.

## Consequences

- Core and App retain separate repositories, tests, and release cadences.
- A Core release artifact is a hard dependency for an RKA App release.
- Local development may build a uniquely tagged Core image from a clean Core
  checkout, but this is test evidence only and must never become a release
  reference.
- Hugging Face configuration, authentication, storage policy, client setup,
  upgrades, and rollback remain later milestones built on this foundation.
