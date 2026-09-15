# User-owned GitHub Codespaces trial

Status: **public image ready, controlled visitor trial awaiting clean acceptance**.
RKA App owns this adapter. Released Core owns all data and public APIs.
RKA remains local-first; this is not a shared hosted service.

**Not deployed in the existing owner Codespace:** the default visitor config now
pulls the [public demo image by immutable digest](demo-image-v1-publication.md),
instead of building Core/features. It inherits one bootstrap hook from that
image. The stable maintainer recipe is `.devcontainer/image/devcontainer.json`.
The image includes a non-root
user, per-container SSH identity, bounded port waiting, sample fetching and
automatic first-use setup. Core 3.0.1 supplies truthful keyword-only status.
See [distribution/migration](demo-distribution.md) before rebuilding the existing
root-owned preview. Historical cloud evidence below applies to batch 3 only.

## Implemented in this candidate

- Immutable Core 3.0.1 image reference, loopback port 7860, isolated persistent
  namespace under `/workspaces/.rka-codespaces-demo/<CODESPACE_NAME>/`.
- Explicit Codespaces identity gate. Manual mode's private-port flag is an
  operator assertion, **not** an automatic GitHub access-control check.
- Opt-in automatic mode uses `gh codespace ports` for the exact Codespace and
  requires port 7860 to be Private. Missing, unknown, duplicate, org or Public
  results, authentication errors and timeouts stop automatic startup. There is
  no automatic fallback to manual confirmation or a copied host token.
- A startup lock serializes launch/enable/disable, and a separate lifetime lock
  covers server, initialization and worker. A second launch or occupied demo
  port leaves the existing process untouched. Startup waits for its own launch
  nonce, not a stale status or a PID read from disk.
- Optional sample import after health/version validation and before worker start.
  A pinned SHA-256 and bounded manifest-only ZIP check precede the public REST
  import. No Core imports, direct DB access or archive extraction. The fictional
  sample is published and first-use provisioning is enabled in the candidate.
  Image publication and anonymous pull are verified separately in the image
  receipt; clean visitor acceptance is still required. An enabled source flag
  alone does not prove any of those external results.
- Durable import intent before POST; successful response and project readback
  before a ready receipt. Restart reuses that project without reimporting,
  renaming, comparing edited counts, or requiring the original ZIP.
- Ambiguous import, corrupt receipt, missing project or changed sample version:
  retain state and refuse automatic retry/reset. Inspect via public Core APIs;
  do not delete the receipt blindly to bypass the guard.
- Child runtime does not inherit repository tokens, cloud credentials, proxy
  variables, local RKA settings, or model endpoints. Embeddings and LLM off.
- Automatic mode keeps only the necessary GitHub CLI auth context in the App
  controller; it is not passed in the Core child environment. This is environment
  isolation, not a separate OS security principal inside the owner's container.
- A welcome guide with Map → Graph → Missions, export, stop and local migration.
- SSH feature 1.1.0 with password/keyboard-interactive authentication disabled,
  empty passwords refused, key-only root login and GatewayPorts disabled. The
  rebuilt owner Codespace's effective `sshd -T` configuration matched these
  settings; only port 7860 appeared in its forwarded-port inventory.

## Historical private operator validation (Core 3.0.0, 2026-09-14)

First inspect the intended Codespace, retain existing work, and verify the pinned
Core image can be pulled. Do not create another billed instance as a workaround.
The `postStartCommand` calls the automatic controller. Without an owned opt-in
record, it starts **no Core process**. On a first visit, the operator must finish
the checks below before enabling automatic resume.

The Core package remains private. The App repository has been granted Codespaces
Read access. The intended owner's existing Codespace successfully pulled this
exact Core digest on 2026-09-14:

```text
ghcr.io/rka-project/rka-core@sha256:f35123dd117e34c9344df022594fbec1bffb42d50a8f2a53d78e58837987a14b
```

The first pull did not build the adapter. A subsequent private batch built it,
ran the 59 tests on Linux / Python 3.13, and started Core with the fictional sample.
These checks do not prove that a new visitor can pull the private package.
Never put a PAT in the repository, build arguments, image, or Docker config.

### Manual foreground validation

In the Codespace, after rebuilding the reviewed adapter:

1. Check port 7860 is **Private** in the Ports panel.
2. Supply only the reviewed fictional pack. For the existing operator upload:

   ```bash
   PYTHONPATH=/opt/rka-app /app/.venv/bin/python -m rka_app.codespaces \
     --confirm-private-port \
     --sample-pack /workspaces/rka-demo-data/research-showcase/rka-research-showcase.rka-pack.zip
   ```

3. Wait for “Sample ready”; open port 7860 and select the named sample project.
   The worker starts immediately after initialization. Check both processes.
4. Verify signed-out access is denied. The environment guard and loopback bind
   do not make a Public forwarded URL private.
5. Follow [WELCOME.md](../WELCOME.md). Stop with Ctrl-C for the foreground
   process; stop the Codespace itself from GitHub when finished.
6. Restart with the same command and verify edits remain. Export through Core
   before deleting a Codespace. There is no reset command.

### Opt-in automatic resume candidate

Do not run this alongside the manual launcher. Stop the foreground launcher
first; enabling refuses a namespace that already has a live runtime owner.

1. In the **actual rebuilt Codespace terminal**, verify `CODESPACES=true`, the
   correct `CODESPACE_NAME`, and an authorized GitHub CLI port query. Inspect only
   variable presence, never print tokens. Confirm that 7860 is listed as Private:

   ```bash
   gh codespace ports -c "$CODESPACE_NAME" --json sourcePort,visibility
   ```

2. Verify the exact fictional sample and opt in. This does **not** start Core:

   ```bash
   PYTHONPATH=/opt/rka-app /app/.venv/bin/python -m rka_app.codespaces_autostart enable \
     --sample-pack /workspaces/rka-demo-data/research-showcase/rka-research-showcase.rka-pack.zip
   ```

3. Start and wait for a fresh running receipt, which follows sample initialization
   and both child processes being observed alive:

   ```bash
   PYTHONPATH=/opt/rka-app /app/.venv/bin/python -m rka_app.codespaces_autostart start
   ```

   Readiness can subsequently change. Open the Private port, select the sample,
   inspect the live dashboard and verify worker liveness. On later resumes,
   `postStartCommand` performs the same guarded start and retains existing data.

4. Inspect the last recorded state when troubleshooting:

   ```bash
   PYTHONPATH=/opt/rka-app /app/.venv/bin/python -m rka_app.codespaces_autostart status
   ```

   `namespace_locked` means some runtime holds this namespace; `last_status` is
   historical, not a fresh health check. A same-nonce receipt is required for a
   newly spawned background launch. No saved PID is used to kill a process.
   After confirming no existing runtime is active, use `run` instead of `start`
   for foreground diagnostics. Background output is discarded; status contains
   only phase, launch identity, project identity, PID and timestamp.

5. To prevent future automatic launches, without deleting data or stopping an
   already running demo:

   ```bash
   PYTHONPATH=/opt/rka-app /app/.venv/bin/python -m rka_app.codespaces_autostart disable
   ```

   Stop the Codespace through GitHub to stop its running services.

The privacy query runs before launch and is checked at 30-second intervals in
steady-state supervision, with a 15-second query timeout. A failed check stops
the controller's owned Core children. This is an operational guard, **not** the
network access boundary: GitHub Private forwarding is that boundary. A visibility
change may expose a port until the next check and bounded shutdown; initialization
is synchronous and can delay checks. Never switch a running demo port to Public.

Batch 3 resolved the observed SSH-context difference: a standard login shell in
the rebuilt owner Codespace had `CODESPACES`, `CODESPACE_NAME` and the platform's
`GITHUB_TOKEN`; its real private-port query succeeded. Bare SSH command execution
is not equivalent to that environment. The first real `postStart` also accepted
the Codespace identity and correctly reported no opt-in, without starting Core.
For CLI troubleshooting, use the normal login shell, not manually copied tokens:

```bash
gh codespace ssh -c <your-codespace-name>
```

Inside that remote terminal, enter a login shell and then run the query:

```bash
bash -l
gh codespace ports -c "$CODESPACE_NAME" --json sourcePort,visibility
```

This is not authorization to read or print token values. The new candidate waits
for absent registration with a bounded deadline, but still rejects public/org,
malformed responses and authorization failures. The existing owner's successful
setup does not establish cold-create ordering or privileges for every visitor.
An actual Shutdown → resume cycle passed for that Codespace without a manual
`start`: a fresh launch identity reached running, both Core children were alive,
and the same sample project and all three view-data hashes were retained.

Core 3.0 selects a project through its dashboard selector/local browser state; it
does not accept an App project-selection deep link. This candidate does not edit
the Core bundle, inject localStorage, or repurpose the default project. A small
public Core navigation contract is a separate follow-up.

## Sample boundary

**UrbanHeat Research Showcase — SYNTHETIC DEMO**

SHA-256: `25f3b45396bdaa9dc3cff9d7a50c2e705204a8c6b2137cfb35927c6b2cc91a0f`

Expected scenario: 4 research questions, 12 clusters, 60 claims, 66 journals,
20 missions and 3 open blocking checkpoints. Supporting and contradicting
records are fictional, not scientific evidence or real PI approval.

The ZIP was initially approved only for the owner's specific Codespace. The
owner subsequently explicitly approved public distribution of this exact
fictional ZIP and a separate demo image. The ZIP is now a public Release asset,
verified by anonymous re-download; see the [publication receipt](demo-showcase-v1-publication.md).
It is not Git-tracked or baked into an image. The smaller historical development
archive remains separate, unchanged, and not approved for public distribution.

## Public release gates — still required

1. Completed: the reviewed Core 3.0.1-based demo image passed the approved image
   pipeline and was published independently. The default visitor config pins it;
   require exact-head consumer CI before merging that configuration.
2. Completed: the separate demo image and fictional ZIP are public and verified
   by anonymous downloads. The existing Core package remains private. Test a
   non-owner account before enabling the homepage visitor path.
3. Completed: exact sample publication, anonymous verification and local download
   gate. No arbitrary URL input, credentials, archive extraction or `latest`
   fallback. The source runtime gate is open, not the homepage visitor path.
4. Extend the successful existing-owner private startup/resume checks to a clean
   new visitor Codespace: lifecycle identity/auth and forwarding registration
   order. Validate remote failure shutdown without introducing public exposure.
   Add a ready-state browser handoff; a welcome file alone does not meet this gate.
5. Add/release a supported project-selection contract in Core, or explicitly
   retain one manual project-selection step in the trial UX.
6. Complete cold-create, failed-start and non-owner browser tests. Existing-owner
   stop/resume, API import/export, effective SSH settings and worker liveness
   passed; credential-free HTTP reached the forwarding sign-in page, not Core.
   Those results are not a substitute for a clean visitor trial.
7. Only then enable a homepage creation/resumption link. Never link visitors to
   the owner's running `app.github.dev` URL. Do not embed a private runtime iframe.

Local Codex/Claude clients do not automatically connect to this cloud trial.
Remote MCP is not part of Core 3.0's supported surface; AI-client setup is optional
later work, not a prerequisite for exploring the dashboard.

## Verification commands

```bash
PYTHONPATH=src python -B -m unittest discover -s tests -v
ruff check src tests scripts
PYTHONPATH=src python -B scripts/demo_seed_smoke.py \
  --core-cli /absolute/path/to/released/rka \
  --sample-pack /absolute/path/to/reviewed/sample.rka-pack.zip
```

The opt-in smoke uses a temporary directory, ephemeral loopback ports, the public
CLI and REST API. It starts/stops its own server and worker, checks import/reuse,
preserves a synthetic edit across restart, inspects Map/Graph/Missions, exports
the project, and compares protected live-container identity/image/mount/state/
health/ports before and after. It never imports Core or opens its DB directly.
If the standalone CLI lacks sqlite-vec, pass an existing shared library with
`--sqlite-vec /absolute/path/to/vec0.dylib` (or the platform equivalent), for test
processes only. An incomplete index-integrity check is not silently accepted.

A local CLI smoke does not validate the pinned Codespaces image or visitor access.
See GitHub's [private forwarding guide](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace),
[package access guide](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility#ensuring-github-codespaces-access-to-your-package),
and [welcome-file configuration](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/configuring-dev-containers/automatically-opening-files-in-the-codespaces-for-a-repository).
