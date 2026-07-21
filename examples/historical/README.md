# Historical Archive

![status: archived](https://img.shields.io/badge/status-archived-6c757d?style=flat-square)
![provenance: W3C PROV](https://img.shields.io/badge/provenance-W3C%20PROV-0b7285?style=flat-square)
![packages: 4](https://img.shields.io/badge/packages-4-1864ab?style=flat-square)
![integrity: SHA-256 verified](https://img.shields.io/badge/integrity-SHA--256%20verified-2b8a3e?style=flat-square)

> **How this project grew.** This folder preserves earlier delivery packages produced
> by the Delivery Engine at specific points in its development. Nothing here is a
> current showcase — for what the engine produces **now**, see the example folders one
> level up in [`examples/`](../). This archive exists to show the **journey**: the same
> discipline — *agent proposes, deterministic tools dispose, human governs, every claim
> traceable* — applied at each stage as the engine matured.

## How this archive is organized

Each folder is named `stepNN_<original-package-name>`. The `stepNN` prefix is the build
step that produced it, so folders sort in the order the work actually happened. The
original package name is kept unchanged, so each package keeps the identity it had when
it was built. **Nothing has been deleted or rewritten** — these are the packages as they
were produced, moved here intact.

## Provenance

Each package is a self-contained, verifiable record, following the Entity–Activity–Agent
pattern of the [W3C PROV](https://www.w3.org/TR/prov-overview/) provenance model, in
plain language:

| PROV concept | In this archive |
|---|---|
| **Entity** — the thing whose origin we track | The package and every file in it, each carrying a SHA-256 digest in its `manifest.json`. Recomputing and matching the hash proves the evidence is unaltered. |
| **Activity** — the process that produced it | The engine run at the build step named in the folder prefix. Each package's `audit_log.jsonl` records every stage, decision, rationale, and timestamp. |
| **Agent** — who was responsible | Built by Mohd Saif Hussain, working with Claude, under the rules of [`PROJECT_CHARTER.md`](../../PROJECT_CHARTER.md). The charter version in force at each step governs that package. |

**To verify any package:** open its `README.md` and `manifest.json`, recompute the
SHA-256 of any file, and compare. Matching hashes mean unaltered evidence.

## The packages

### `step04_example_package`
The first end-to-end thin slice. **Churn analysis** for a retention team, run on a
telecom churn dataset. Headline: **4 rules evaluated, 13 exceptions** — reported, never
dropped. The engine's earliest complete package: executor, findings store, and
hash-verified manifest working together for the first time.

### `step05_example_package_dq`
The second archetype arrives. A **data quality review** of a vendor extract, introducing
the `rules_draft` stage (the content-bound Human Gate 2). Headline: **7 rules evaluated,
0 exceptions** — a clean dataset, shown honestly as clean.

### `step18_example_package_math`
A **universal descriptive audit** — distribution shape, outliers, entropy, temporal
structure — run on `orders.csv`. Headline: **1 rule evaluated, 0 exceptions**.
`orders.csv` is the same source file that today seeds the
[`universal_audit`](../universal_audit/) example, so this is an earlier run of data the
current examples still use.

### `step18_example_package_stats`
A **segment comparison with statistical significance** for a growth team, run on
`signup_conversion.csv`. Headline: **1 rule evaluated, 0 exceptions**.
`signup_conversion.csv` is the same source that today seeds the
[`segment_comparison`](../segment_comparison/) example — again, an earlier run of data
the current examples still use.

---

Both Step 18 packages were produced at the same build step, which is why they share the
`step18` prefix. Their source files remaining in active use is not a coincidence to hide
but a small piece of the project's real lineage: the data these early packages examined
is the same data the mature engine examines now.
