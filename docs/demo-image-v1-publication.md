# First independent Demo image — public, anonymous pull verified

Readback: 2026-09-15 UTC. Publication and anonymous full-image download have
passed. This is not a clean-Codespace or homepage-launch receipt. No existing
owner Codespace or local RKA was rebuilt.

## Exact artifact

- Package: `ghcr.io/rka-project/rka-demo`, ID `15087394`.
- Visibility: **public**, with exactly **one** version.
- Version ID: `1249358351`.
- Tag: `sha-72634acb75669f90b8cf29bf0f1fd793a89f08aa-run-34920780180-1`.
- Consumer reference, verified anonymously after organization policy restoration:

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

## Public visibility and policy restoration

With the user's explicit action-time approval, Public package creation was
temporarily enabled, **only `rka-demo`** was made public, and the original policy
was immediately restored and saved. GitHub confirmed the organization settings
update; the final policy permits only private package creation:

- Public package creation: unchecked.
- Private package creation: checked (fixed).
- Internal package creation: unchecked.
- Default inherited source-repository access: checked.

API readback confirmed `rka-demo` is public with the same single version and
`rka-core` remains private. The organization's public container package list
contains only `rka-demo`. No other package access or visibility was changed.
The approved main-only `demo-release` environment and App's **Read-only** Actions
grant on Core remain outside this visibility change.

Package publication is irreversible: restoring the creation policy does not
make the existing demo package private again.

## Anonymous full-image verification

- Downloaded the exact manifest, configuration and all **19** image layers via
  the registry API after the organization policy was restored.
- Verified SHA-256 digests and declared byte sizes for every layer, totaling
  **258,465,349 compressed bytes**; the manifest digest remained the approved
  `aabf3c5f...` digest above.
- Verified Linux/amd64, the exact App revision and the Core image-reference
  provenance label against the approved values above.
- Used an empty process environment and an anonymous, pull-scoped registry
  bearer, with no account token, credential helper, cookie jar or proxy.
  Redirects were HTTPS-only, restricted to registry/blob hosts, and stripped
  authorization headers.
- Streamed and hashed the layers without storing them, extracting files,
  accessing the Docker daemon or starting a container. This verifies anonymous
  registry distribution, not a new Docker-engine or Codespace startup.

## Remaining launch gate

The visitor configuration now pins the verified digest and inherits the image's
single startup hook. The renderer no longer repeats that hook. Require green
exact-head consumer CI/merge, then obtain approval for any billed fresh/non-owner
Codespace acceptance test.
Keep the homepage launch path disabled until acceptance.
