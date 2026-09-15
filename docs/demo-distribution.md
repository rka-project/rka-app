# User-owned demo distribution and non-root migration

Status: **fictional sample published; image/runtime still an implementation
candidate, not rebuilt in the owner's running Codespace**. See the
[publication receipt](demo-showcase-v1-publication.md). Core and App remain separate release units. No real research
pack, credential, local database or model cache is part of this distribution.

## This batch

- The development shell and lifecycle hooks use `codespace` (UID/GID 1000), with
  Dev Containers UID alignment enabled and common-utils 2.5.9 pinned. No global
  Git wildcard trust entry or recursive workspace/database ownership rewrite.
- Owned state must belong to the current OS user and be mode 0700. Old root-owned
  state is retained and refused, not silently adopted.
- First setup/resume retries absent port registration for up to 60 seconds plus
  a final bounded CLI query (15 seconds). Public/org, duplicate/malformed results,
  missing authorization and CLI errors fail immediately. Core does not start
  while waiting. If registration times out, forward 7860 as Private and retry
  bootstrap. The adapter never changes visibility.
- Public first-use provisioning is implemented but **release-gated off**. Once
  released it fetches the exact fictional ZIP, verifies it, writes the opt-in,
  and starts the supervisor. Resumes preserve disabled/corrupt/uncertain state;
  no automatic reset, reimport or re-enable after opt-out.
- Downloads use HTTPS without proxy/auth/cookie environment, the exact Release
  URL and only its `release-assets.githubusercontent.com` redirect host. Limits:
  4 MiB ZIP, 16 MiB manifest, 10-second socket operations, 60-second transfer
  budget plus the current bounded read, three redirects. SHA-256 and manifest
  identity are checked before atomic no-clobber caching. No archive extraction.
- A manual, main-only image workflow verifies the exact reviewed head, defaults
  to no publication, builds all features, then tests the image as non-root with
  no external network. It also imports the verified sample through Core REST,
  checks lexical capabilities and views, edits/exports, and restarts both Core
  processes with disposable state. Each run/attempt receives a distinct image
  tag; consumers must still use its digest. Visitors will pull that image rather
  than rebuilding Core, apt packages and features on their billed machine.

## Approved public artifacts — sample published, image pending

1. A **new, separate** `ghcr.io/rka-project/rka-demo` package with reviewed App,
   Dev Container features and a pinned released Core. Do not change visibility
   of the existing private `rka-core` package or its historical versions.
2. `rka-project/rka-app` Release `demo-showcase-v1`, asset:

   ```text
   rka-research-showcase.rka-pack.zip
   SHA-256 25f3b45396bdaa9dc3cff9d7a50c2e705204a8c6b2137cfb35927c6b2cc91a0f
   ```

   URL: `https://github.com/rka-project/rka-app/releases/download/demo-showcase-v1/rka-research-showcase.rka-pack.zip`.
   This is **UrbanHeat Research Showcase — SYNTHETIC DEMO**, not the historical
   RKA development archive. Distribute it as a release asset, not Git-tracked
   data. Asset URLs alone are not immutable; the pinned SHA rejects replacement.

Public GHCR images allow anonymous pull. Making a package public is irreversible
under [GitHub's current package-visibility policy](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

## Release order — in progress

1. Review/merge the **separate Core UI fix**, then release through Core's existing
   CI/container pipeline. App must not copy a patched Core bundle. Update App's
   FROM/provenance digest, `SHOWCASE.core_version` and associated pin tests to
   that released version. Current App still consumes Core 3.0.0 and its old UI.
2. **Completed:** approval for both exact artifacts; fictional ZIP publication;
   anonymous download and SHA/manifest verification. The image pipeline does
   not upload the ZIP or read any historical real-data pack.
3. Sample downloading is enabled locally (`PUBLIC_SAMPLE_ENABLED=True`). Keep
   `PUBLIC_DEMO_ENABLED=False` until the Core/App runtime release gates pass.
   The `demo-release` environment now requires maintainer approval and allows
   only the `main` branch. The maintainer explicitly approved same-account
   dispatch/review. App's Actions access to the Core package is **Read** only;
   the existing Codespaces Read grant and private package visibility are unchanged.
   These settings were read back after configuration on 2026-09-15; the YAML
   itself cannot establish the repository's environment-review rules.
4. Dispatch `reviewed-demo-image` with the exact main SHA and `publish=false`.
   Confirm build, non-root tests, Git and real Core restart checks. After approval,
   dispatch with `publish=true`; the public sample gate runs first. Separately
   approve/set visibility for **only the new demo package** and verify an
   anonymous pull of its resulting digest. The workflow never changes visibility.
5. Render a visitor config using the verified published digest:

   ```bash
   python scripts/render_codespaces_config.py --image ghcr.io/rka-project/rka-demo@sha256:<verified-digest>
   ```

   Review its output before replacing `.devcontainer/devcontainer.json`. Keep
   `.devcontainer/image/devcontainer.json` as the stable build recipe. The
   renderer preserves non-root/forwarding policy and drops `build`/`features`;
   those features already reside in the prebuilt image and its metadata.
6. With approval for any billed resource, test a **fresh non-owner** Codespace:
   image/sample fetch, startup, Private browser access, denied signed-out/other-
   user access, both processes, Map/Graph/Missions, edit/export, stop/resume and
   missing-port/network-failure recovery. Local tests are not that proof.
7. Only then enable the homepage's create-your-own-Codespace link. Never point
   visitors at the owner's live forwarded URL. One manual sample-project
   selection remains required in Core's dashboard.

The prebuild mechanism follows the [official Dev Container CI workflow](https://github.com/devcontainers/ci/blob/main/docs/github-action.md).
It targets Codespaces Linux/amd64, not a general desktop release or local-Core
installation change. Workflow publication and cloud image build remain untested.

## Existing root-owned preview — preserve before migration

**Do not rebuild the existing owner Codespace into this non-root candidate yet.**
Its state root `/workspaces/.rka-codespaces-demo` belongs to the old root
controller. Changing `remoteUser` does not migrate file ownership or a database.

Migration requires a separate, target-checked operation:

1. Export the selected project through Core's public export UI/API, verify the
   archive, retain it privately, and preserve uncommitted repository work.
2. Disable automatic resume with the old controller and stop the Codespace.
   Do not copy a live SQLite file, recursively chown it, or delete receipts.
3. With no old runtime active, retain the exact old state under an explicitly
   approved backup name, rebuild, and let the new user create a fresh private
   root. Retain the original until exported/imported content is verified.
4. Start in manual mode without sample seeding and import the verified export
   through Core's public API/UI. Compare counts and representative graph/map/
   mission data. The automatic sample controller does not adopt arbitrary
   imports; keep the migrated operator project manual until a reviewed adoption
   procedure exists. Fresh visitors do not need this migration.

For read-only diagnosis in the **inspected old root preview**, use a per-command
Git exception scoped to the known checkout, never a global wildcard:

```bash
git -c safe.directory=/workspaces/rka-app -C /workspaces/rka-app status --short --branch
```

The fresh-user test must confirm normal Git works without that exception.

## Evidence and limits

Isolated local checks cover App unit tests/ruff and a released Core 3.0.0 CLI
smoke: temporary data/ports, import, reuse after editing/restart, Map/Graph/Missions
and export. Protected production container identities/images/start times/mounts/
ports remain unchanged. Separate Core checks cover status resolver tests,
frontend build/typecheck and capabilities-route tests with an existing sqlite-vec
library supplied to test processes only.

Batch results: **80 App tests, 7 Core UI status tests, 10 capabilities-route
tests passed**, plus the frontend production build and the two-cycle real Core
CLI smoke. The first capabilities run lacked sqlite-vec (9 passed/1 failed);
supplying the existing library to the isolated test process produced 10/10.

The 80 App tests and Ruff passed locally. PR #2 passed all seven CI jobs across
Linux, Windows and macOS and was merged at
`09112af449ecd04fd63bb0965bc7d575712e9077`. The configured approval gate precedes
the first no-publication image validation; that run is not a runtime release.

First dry run `34916443679` successfully pulled the private Core base and built
the complete feature image, but explicit `platform` made the pinned action
export OCI rather than load the local Docker image. The image tests therefore
failed before running; nothing was published. The follow-up uses the checked
native Linux/X64 runner, inspects the locally loaded image/architecture, and
sets `docker run --pull never` so missing local output cannot trigger a pull.

Second dry run `34917101541` loaded the Linux/amd64 image and passed all 80 tests
inside it as `codespace`. The subsequent shell check failed; it incorrectly
required `/usr/local/bin/gh`, whereas the feature installs the official Debian
package. The follow-up checks the same trusted PATH as the runtime privacy guard,
executes/verifies GitHub CLI 2.98.0, and prints non-sensitive identity/tool-path
readbacks. All-source Git wildcard rejection and the real Git operation remain
required. The Core import/restart image smoke has not passed yet.

A local prebuilt-image validation was attempted with Dev Containers CLI 0.89.0
using the exact private Core digest and a unique test tag, without `--push` or
any runtime/container start. GHCR returned **401 authentication required** before
the image could build. No image-success claim is made; registry credentials and
package visibility were not changed. Re-run via the authorized App build context
or separately approved registry access before deployment.

The Core dependency lock is unchanged. `npm audit` reports pre-existing dependency
advisories; this targeted patch is not a dependency-security clearance and does
not perform broad upgrades. Public sample availability is verified; public image
availability, new-user cold create, root-state migration and other-user browser
authorization are not yet verified.
