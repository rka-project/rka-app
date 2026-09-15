# Codespaces trial: validation record

## Published-image consumer configuration — local validation (2026-09-15)

Scope: App's isolated checkout only. No new or rebuilt Codespace, local Core
change, model startup, package-permission change or homepage deployment.

- The independent demo image and fictional sample are already public; see the
  [image receipt](demo-image-v1-publication.md) for the exact digest and anonymous
  full-image verification. Core 3.0.1 is baked into the image.
- The default visitor config now references only that image, not a Dockerfile
  or Features build. Maintainers retain the separate image build recipe.
- Anonymous inspection of the actual image confirmed its metadata already
  contains the bootstrap hook. Dev Containers accumulates lifecycle commands;
  the renderer now omits a duplicate `postStartCommand` and rejects an unexpected
  source hook. A regression test requires exactly one inherited bootstrap.
- **88 unit tests and Ruff passed locally** on macOS / Python 3.12. Unit tests
  used temporary state/ephemeral test ports; no production data or Docker daemon.
- Added a separate CI consumer job for anonymous Docker pull, real merged
  metadata (CLI 0.89.0), installed App tests (no source override), non-root Git/gh,
  and isolated Core import/graph/map/missions/edit/restart checks. Local success
  is not proof of this job; its exact-head green run is required before merge.
- Fresh visitor lifecycle/private-port behavior, non-owner access and actual
  Codespace stop/resume remain gated. The homepage launch link stays disabled.
- The first push at `ddbd213` was rejected by workflow validation (run
  `35012116512`), before any job ran: `runner.temp` is not available in job-level
  `env`. The follow-up exports the anonymous Docker config through `GITHUB_ENV`
  from a runner step and adds a regression assertion. That failed run is not
  test evidence; the corrected head must pass the complete CI suite.

## Batch 3 — real owner Codespace validation (2026-09-14)

Scope: only the maintainer's existing private Codespace in `rka-project/rka-app`.
No new Codespace, Git commit/push, public package/sample publication, public port,
homepage deployment or local production RKA change. The candidate **was uploaded
and privately deployed for testing**; remote Git remains uncommitted.

### Build, access and runtime checks passed

- Verified a clean remote tree at `9b56644c2681f57fc4b9fb8c027a5d998a28da43`
  before applying the candidate. Saved original tracked files in
  `/workspaces/rka-demo-validation/batch3-20260914/original-tree.tar`
  (SHA-256 `2cc62f28e66b0304f53e4f9d5a87cfcae59d5be594be76ffda18d1211d8f0d3e`).
  No Git history was reset or replaced.
- Candidate transport archive SHA-256:
  `1eb028ad636c21f56f8b8d534b58b4c524d3895264ef9045856b6a1cd4dcbbf0`.
  It contained App code/config/tests/docs, no `.git`, sample ZIP, database or
  credentials. Later documentation refinements are separate from this snapshot.
- Ordinary rebuild (not full rebuild) succeeded from the exact Core digest.
  Built image ID:
  `sha256:81a562f545028f9c83e15f7287f72a2c380270a7476c8e8674e57f15ecfc1c4d`.
  Runtime readback: Core 3.0.0, Python 3.13.15, GitHub CLI 2.98.0. Installed App
  autostart/privacy source hashes matched the uploaded local candidate.
- Real first `postStartCommand` completed successfully and reported
  `disabled: no opt-in record; nothing started`.
- All 59 tests passed inside the rebuilt Linux container. They did not use
  production ports, data or containers. Windows execution remains unverified.
- Effective SSH readback: port 2222, password/keyboard-interactive/empty-password
  authentication disabled, root key-only, GatewayPorts disabled. The GitHub
  forwarded-port inventory listed only 7860, with visibility `private`.
- The standard login shell had platform identity and token variables, and its
  actual `gh codespace ports` query succeeded. Only variable-presence booleans
  were inspected; no tokens were printed, copied from the host or added to files.
- Explicit `enable` and `start` succeeded with the pinned fictional sample.
  Fresh running receipt:
  `prj_demo_283d87226b3349c6973e202996f69d43`, launch
  `c91eb07662184dd28000fbc1745f9dd5`. Both `rka serve` (loopback 7860) and
  `rka worker` were observed under the same App controller. Repeated `start`
  reused it, leaving both PIDs and the launch identity unchanged.
- Public REST checks: health 3.0.0 / ok; two projects (default plus one sample);
  graph 189 API nodes / 386 links; Research Map and Missions responses; valid
  project export with 20 missions, 60 claims, 66 journal records, 12 clusters,
  16 decisions and three checkpoints. No direct Core DB access.
- Browser readback: sample project selected through the supported dashboard UI;
  Research Map displayed 4 questions / 12 clusters / 60 claims / 4 contradictions;
  Missions displayed 7 active / 20 total and task progress. Knowledge Graph
  rendered 126 nodes / 326 connections by default, and 186 / 386 with Claims
  enabled. Welcome instructions now explain that layer switch and zoom controls.
- A cookie-free, credential-free HTTP request did not return Core health data:
  it redirected to the Codespaces `/pf-signin` authentication page. The browser
  separately completed its private forwarding session and could open the demo;
  that browser is **not** an anonymous/non-owner access test.

### Stop/resume passed

- Stopped the RKA Codespace and waited for an actual `Shutdown` readback. The
  unrelated Codespace remained Shutdown throughout.
- Resumed only RKA via SSH. Did **not** run App `start` or `enable` after resume.
  The actual `postStart` controller produced a fresh launch identity
  `97ac72d9e2ef40c2bb8a74c85b168931`, transitioned starting → running, and started
  both Core children. Server PID 351 and worker PID 388 shared controller PID 187.
- Reused the exact project ID `prj_demo_283d87226b3349c6973e202996f69d43`;
  project count stayed two (default plus sample), with no duplicate import.
  Export integrity and counts passed again. Source ZIP SHA-256 was unchanged.
- Canonical JSON hashes were identical before and after the real stop/resume:
  - Graph: `ef20fa5cb64422bbb0b22598d7457b4e2cd342a7e3ab538fde44a9c41202a51f`
  - Map: `d03efde35d8ae3008393d64934b288828949ec08eb8512331a4cfcd23d5b7f9d`
  - Missions: `6951f6c294b7c40d5bce9d6918c505afbabf49271546de1a12afce8a8a9c175a`
- RKA is intentionally left running for owner testing after this verification;
  unrelated Codespaces stay stopped. Use the owner's Codespace page to stop it
  when finished. This instance is not linked from the public homepage.
- The browser reconnected through private forwarding after resume and again
  displayed 7 active / 20 total missions. The local protected server/worker IDs,
  images, start times, mounts, state/health and ports matched the pre-test baseline;
  Core main retained only its pre-existing untracked demo directory.

### Remaining limitations

- One existing owner's private Codespace is not a clean new/non-owner trial.
  Public artifact distribution, checksum-pinned sample fetching and the homepage
  creation link are still gated. The homepage was not changed in this batch.
- The Core first-run semantic-search banner is misleading for this embeddings-off
  demo. The App welcome guide warns about it; Core's UI was not patched in App.
- Rebuilding this pre-existing default Codespace changes its runtime user to root,
  while the persisted Git checkout retains its old owner. Git therefore refuses
  ordinary commands with its dubious-ownership guard. This does not prevent the
  demo/API from running, but the public template still needs consistent user and
  workspace ownership. No recursive ownership change or global Git trust exception
  was applied; read-only Git verification uses a one-command exception for the
  exact previously verified checkout only.
- Periodic privacy checking is an operational safeguard, not instantaneous network
  enforcement. No Public-port exposure was introduced to test failure behavior.
  Windows tests and a full remote security review are not claimed.

## Batch 2 — opt-in resume and live pull verification (2026-09-14)

Scope: local App candidate only. The earlier homepage candidate was not changed
in this batch. No commit, push, merge, public image/sample publication, homepage
deployment, remote App code upload, adapter rebuild or remote Core startup.

### Passed

- 59 unit/regression tests on macOS / Python 3.12, plus Ruff and Git whitespace
  checks. New coverage: exact private-port query, auth failure and timeouts,
  missing/duplicate/malformed/non-private results, periodic recheck, opt-in-only
  startup, startup/lifetime locks, stale receipt rejection, fresh launch identity,
  controller/Core credential separation, exact-child timeout cleanup, disable
  without data deletion or process signaling, and worker startup failure.
- The configuration-only enable test mocks the POSIX lock so it remains suitable
  for Windows CI; real lock tests are POSIX-only. Windows/Linux tests have not
  been executed in this batch.
- Real released Core CLI smoke rerun: two disposable startup cycles, public REST
  sample import/reuse, Map/Graph/Missions and export checks, and preservation of
  a synthetic edit across restart. Core reported 3.0.0. The test used separate
  temporary storage and ephemeral loopback ports, with the existing sqlite-vec
  library supplied to test processes only. Embeddings remained off.
- Protected production container snapshots matched before and after the smoke.
  Core main and the pre-existing untracked demo files were not modified.
- The intended maintainer RKA Codespace successfully
  pulled Core's pinned digest:
  `sha256:f35123dd117e34c9344df022594fbec1bffb42d50a8f2a53d78e58837987a14b`.
  The earlier App repository Codespaces Read grant therefore worked for this
  owner's pull. No private package visibility change was made.
- The existing remote fictional ZIP still matched SHA-256
  `25f3b45396bdaa9dc3cff9d7a50c2e705204a8c6b2137cfb35927c6b2cc91a0f`.
- The RKA Codespace was stopped after readbacks and the image pull. Fresh `gh`
  inventory confirmed both it and the unrelated Codespace were
  **Shutdown**. Only the RKA Codespace had been resumed for this batch.

### Still gated

- The remote SSH shell had `CODESPACES`, but no `CODESPACE_NAME`, `GH_TOKEN` or
  `GITHUB_TOKEN`; its port query requested GitHub CLI authorization. The authorized
  host CLI returned an empty port list. No host token was copied. This SSH result
  does not establish the actual browser-terminal or `postStart` environment.
- The real adapter container has not been built. Automatic resume has unit-test
  coverage, not Codespaces end-to-end proof. Lifecycle identity/authentication,
  forwarding registration order, effective SSH settings, worker liveness and
  signed-out denial still require a reviewed rebuild and live readback.
- Private-port checks fail closed, but are not an instantaneous network firewall.
  They run before startup and during steady supervision; see the timing caveat
  in [codespaces-demo.md](codespaces-demo.md). No automatic downgrade to the
  operator-confirmation flag is implemented.
- Public image/sample distribution and non-owner access, automatic verified
  fetching, ready-state browser handoff and an enabled homepage launch button
  remain unimplemented/unverified. The private image pull does not clear these.

The security-guidance review shaped fail-closed checks, credential environment
isolation and exact-process ownership. It is not a security certification or a
completed remote access test.

## Batch 1 — initial local candidate (2026-09-14)

Historical record below; batch 2 above updates its pending items.
Scope: App candidate and GitHub Pages homepage candidate.
No commit, push, merge, package publication, homepage deployment, Codespace start,
or production runtime mutation was performed in this implementation batch.

### Passed

- 36 unit/regression tests on macOS / Python 3.12. Covers guards, credential
  isolation, namespace ownership, simultaneous launch, occupied ports, sample
  hash, size limits, symlinks/FIFOs, receipts, uncertain outcomes, deleted projects,
  strict integrity warnings, optional supervisor initialization and cleanup.
- Ruff across src/tests/scripts and Git diff whitespace checks.
- Real installed Core CLI reporting 3.0.0, two disposable startup cycles with
  separate temporary storage and ephemeral loopback ports. Used an existing
  cached sqlite-vec shared library in the test processes only; no installation
  changes and embeddings off.
- Exact reviewed fictional ZIP imported through public REST; same project reused
  on restart. A synthetic summary edit persisted. Map/Graph/Missions API results
  matched across restart. Keyword search for calibration returned results.
  Exported ZIP integrity and 20 missions / 60 claims checked. Both server and
  worker were started and stopped only in the disposable test environment.
- Protected rka-server/rka-worker identity, image, mounts, start time, state,
  health and ports matched before/after each real CLI smoke.
- Core main stayed unchanged except its pre-existing untracked demo directory.
  Both original development-pack and fictional showcase SHA-256 values remained
  unchanged. No sample ZIP or database was added to the App checkout.
- Homepage static build, TypeScript and export verifier passed (69 output
  entries). Lint: zero errors; one pre-existing postcss anonymous-export warning.
- Browser checks: hero link reaches #try; three readable walkthrough panels;
  disclosure control collapses; launch button disabled; no shared-instance link
  or iframe. At 390px width, document scrollWidth is 390px. Desktop rendering
  inspected at the normal 1280px viewport. Captured browser error/warning log empty.

### Findings addressed

- Core returns five additional empty installation-local table counts. Count
  comparison now ignores only zero rows; nonzero mismatches still stop startup.
- A missing sqlite-vec extension produced index_check_incomplete. The adapter
  did not suppress that warning. The corrected disposable environment passed
  the unchanged strict integrity gate.
- FIFO input is opened nonblocking and rejected as non-regular, avoiding a hang
  before file-type validation. No archives are extracted.

The security-guidance review shaped these bounded checks; it is not a security
certification or a completed remote access/penetration test.

### Not verified / not implemented at the end of batch 1

- Actual build/pull of the pinned Codespaces container, effective SSH settings,
  signed-out denial, and non-owner account access.
- Public image/sample distribution, automatic verified fetching, automatic
  startup/privacy readback, ready-state browser handoff, and public launch link.
- Core-supported project-selection deep link. Current preview requires one
  explicit project selection; App does not inject browser storage.
- Windows/Linux execution of these new tests (CI matrix is prepared, not run).
- Semantic retrieval, AI-client wiring, Hugging Face, or desktop packaging.

At that stage the devcontainer deliberately stayed idle. See current gates and reproduction
commands in [codespaces-demo.md](codespaces-demo.md).
