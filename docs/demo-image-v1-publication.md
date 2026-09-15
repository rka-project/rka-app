# First independent Demo image — uploaded, still private

Readback: 2026-09-15 UTC. This is not an anonymous-pull, clean-Codespace or
homepage-launch receipt. No existing owner Codespace or local RKA was rebuilt.

## Exact artifact

- Package: `ghcr.io/rka-project/rka-demo`, ID `15087394`.
- Visibility: **private**, with exactly **one** version.
- Version ID: `1249358351`.
- Tag: `sha-72634acb75669f90b8cf29bf0f1fd793a89f08aa-run-34920780180-1`.
- Consumer reference, pending anonymous access verification:

  ```text
  ghcr.io/rka-project/rka-demo@sha256:aabf3c5f04ec01bc5adc3c31d9634e4db2f299c3b375fdddeddb5bd8ad7b14ae
  ```

- App source: `72634acb75669f90b8cf29bf0f1fd793a89f08aa` (PR #6 merge).
- Core: **3.0.1**, runtime index
  `sha256:19a7ac4098e536930d395a1730ad5b57b082f769e784b40221312bc93cad00f7`.
- Platform: Linux/amd64, intended for Codespaces, not a general desktop image.
- Public fictional ZIP remains a separate pinned Release asset, not baked into
  the image or tracked in Git. See [its receipt](demo-showcase-v1-publication.md).

## Verified

- Core release run `34918034712`, attempt 2: successful architectures, exact
  digest startup smoke and provenance verification. The first attempt's QEMU
  illegal-instruction failure remains in its cancelled run; no tag was rewritten.
- App PR #6: all seven checks passed at
  `339d4c89d71c9048c227c9fdbf8c469f5669c2c6` before the exact-head merge.
- No-publication run `34920599185`: **success** at the final App source SHA.
- Publication run `34920780180`: **success**, same source SHA; all tests repeated
  before pushing its unique image tag.
- Both runs: 86 unit tests in the image; non-root Git and gh; matching App OCI
  revision; two real Core 3.0.1 import/reuse/edit/export/restart cycles; lexical
  capabilities and Map/Graph/Missions; no baked SSH host keys in any saved image
  layer; distinct SSH host identities across containers and stable repeat startup.
- Runtime tests used disposable, network-disabled containers, with no published
  port, user database, credential environment or Docker socket mounted inside.
- The existing `rka-core` package remains **private**. Protected local container
  identities, images, start times, volume and 9712 mapping were unchanged.

## Current authorization boundary

The organization policy currently permits only private package creation:

- Public package creation: unchecked.
- Private package creation: checked (fixed).
- Internal package creation: unchecked.
- Default inherited source-repository access: checked.

Consequently the new package's Public visibility option is disabled, even for
the active organization-admin account. No organization setting was changed.
The approved main-only `demo-release` environment and App's **Read-only** Actions
grant on Core have already been configured and read back.

Before proceeding, obtain explicit action-time approval to temporarily allow
organization members to publish public packages, expose **only this rka-demo
package**, then restore the organization policy. This briefly widens the
organization's package-creation permission; package publication is irreversible.
Read back the policy and both package visibilities afterward.

After that: anonymously pull the exact Demo digest, render/review the visitor
configuration, run CI/merge, and obtain approval for any billed fresh/non-owner
Codespace acceptance test. Keep the homepage launch path disabled until acceptance.
