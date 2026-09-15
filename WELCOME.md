# Your RKA research demo

**Developer preview — public one-click startup is not released yet.**
The newest source candidate uses a non-root development user. Existing root
previews must follow [the migration runbook](docs/demo-distribution.md) before
rebuilding; automatic startup never rewrites ownership of an existing database.
The first start stays idle until the operator completes the private-start procedure
in [the deployment guide](docs/codespaces-demo.md). Automatic resume is an opt-in
candidate: it requires a fresh Private-port check and reuses existing sample data.
Opening this file or seeing a saved status is not a server-ready signal. Do not
enter credentials to work around an image-pull error.

After the separate public-release gate is opened, a fresh Codespace will fetch
the checksum-pinned fictional sample and start automatically. Until then,
bootstrap stays idle without an existing opt-in. If port registration times out,
forward 7860 as **Private** in the Ports panel and retry bootstrap; do not change
the visibility to Public. This is bounded retry, not an endless startup loop.

The intended trial runs in **your GitHub Codespace**, not RKA Project's server.
Use only fictional or non-sensitive content here. RKA remains local-first.

## Once the foreground launcher reports “Sample ready”, or `start` reports “running”

Open **Ports → 7860 → Open in Browser**, keeping visibility **Private**.
Select **UrbanHeat Research Showcase — SYNTHETIC DEMO** in the project selector.
Core 3.0 currently requires that selection; this preview does not change browser
storage or pretend the project was selected for you.

If automatic startup fails, leave the data in place. Ask the operator to inspect
`status` and retry with the foreground `run` command in the deployment guide.
Do not make a port Public to bypass a check. A saved `running` status can be old;
confirm the live dashboard is accessible through the Private forwarded port.

### 1. Research Map: understand the question

Explore four fictional questions about heat-sensor calibration, coverage,
alerting, and reproducibility. Open an evidence cluster and inspect the claims
and source records. A contested cluster is not an approved conclusion.

### 2. Knowledge Graph: follow a disagreement

In the graph's **Layers** panel, enable **Claims** (off by default). Use **Fit
View**, then zoom into one cluster to read its nodes. The default layers show
126 nodes / 326 connections in this fixture; adding Claims shows 186 / 386.
These are view counts, not the full API graph's record count.

Follow supporting, contradicting, and qualifying links. Compare a broad claim
with a counterexample under missing sensor data. The scenario contains 60 claims
and 12 clusters; counts in individual views can differ because their filters differ.

### 3. Missions: see what remains unresolved

Inspect an active mission's progress and an open checkpoint. There are 20 scripted
missions in mixed states and three open blocking checkpoints. These are fictional
records, not real approvals or instructions to execute experiments.

Try keyword search for **calibration**, **outages**, **abstention**, or **retention**.
This demo turns embeddings off and requires no model download or AI API key.
If the Core first-run banner describes semantic search, that is not this demo's
runtime status. No Codex or Claude client is automatically connected.

## Keep your work, then stop the machine

- Ordinary restarts reuse the imported project; no automatic reset or reimport.
- Export the selected project through Core before deleting a Codespace. Keep the
  ZIP private. To move to local RKA, use a compatible Core version and its Import UI.
- **Closing the browser tab does not stop the Codespace.** Use GitHub's Codespaces
  page to stop it. Stopped Codespaces still consume storage; deletion loses their
  local data. Quotas and any charges belong to the applicable GitHub billing owner.
- Disabling automatic resume affects future launches only; it does not stop an
  already running Core. Stop the Codespace to stop its running demo.
- For private or unpublished research, follow the
  [local installation guide](https://github.com/rka-project/rka-core/blob/main/INSTALL.md).

See GitHub's [stop/start guide](https://docs.github.com/en/codespaces/developing-in-a-codespace/stopping-and-starting-a-codespace)
and [billing guide](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces).
