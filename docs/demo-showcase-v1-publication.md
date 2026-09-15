# UrbanHeat public sample publication receipt

The owner explicitly approved public distribution of the separate `rka-demo`
image and the exact UrbanHeat fictional sample ZIP. This approval does not cover
the historical real development archive, production research data, or making
the existing private `rka-core` package public.

## Completed

- Repository: `rka-project/rka-app` (public).
- Release: [demo-showcase-v1](https://github.com/rka-project/rka-app/releases/tag/demo-showcase-v1).
- Release ID: `388788357`; published `2026-09-15T00:20:48Z`.
- Type: sample-data **prerelease**, not a stable App/container release or Latest.
- Tag target: `9b56644c2681f57fc4b9fb8c027a5d998a28da43`; main was not changed.
- Sole uploaded asset: `rka-research-showcase.rka-pack.zip`, asset ID `564512766`.
- Size: **38484 bytes**.
- SHA-256: `25f3b45396bdaa9dc3cff9d7a50c2e705204a8c6b2137cfb35927c6b2cc91a0f`.
- Download: `https://github.com/rka-project/rka-app/releases/download/demo-showcase-v1/rka-research-showcase.rka-pack.zip`.

The exact local ZIP was copied into a private staging directory, verified, and
uploaded to a draft. GitHub's returned asset digest/size/name were checked before
publication. After publication, the App downloader retrieved the public URL with
no authorization/cookie/proxy handlers and validated SHA-256 and the manifest:
60 claims, 20 missions, 66 journal entries, 12 clusters and 386 entity links.
No archive was extracted or imported into a live RKA instance. The original
ZIP remains untracked and unchanged; it was not added to Git history.

## Still pending

The separate `rka-demo` image is **approved for eventual public distribution but
not published**. Core's runtime-status correction and App's image workflow are
still local changes; GitHub's App main remains the initial commit, and Core's
latest published release is still v3.0.0. No source merge, Core release, workflow
dispatch, package-visibility change, Codespace rebuild or production restart was
performed as part of sample publication.

The existing `rka-core` package was read back as **private, 7 versions** after
publication. The `rka-demo` package did not exist at preflight. Public sample
availability is now separate from the closed public-runtime bootstrap gate:
`PUBLIC_SAMPLE_ENABLED=True`, `PUBLIC_DEMO_ENABLED=False`.

The local regression suite passed **79 tests** plus ruff after separating those
gates, including a test that a public sample cannot start an unreleased runtime.

Before publishing the image, finish the separate Core and App review/CI/release
chain, build/test the non-root image, then verify anonymous pull of the approved
new package. Keep the existing root-owned operator preview untouched until its
separate export-and-migration procedure is approved and verified.
