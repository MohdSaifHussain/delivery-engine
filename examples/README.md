\# Examples



> Committed output packages from actual engine runs, verifiable by hash.



\## Background



Each subdirectory is a complete output package the engine produced on a

real dataset, checked into the repository so the results can be read and

verified without running anything. Every package includes a

`manifest.json` whose SHA-256 tree covers every file in the package.

Recomputing a file's hash and comparing it against the manifest confirms

the evidence is unaltered; re-running the example and comparing hashes

confirms the findings are reproducible.



\## Usage



From the repository root, after completing the install in

\[`QUICKSTART.md`](../QUICKSTART.md):



```bash

python examples/churn\_analysis/run\_example.py

```



Each folder's own `README` documents that example in full.



\## Examples



| Folder | Playbook | Summary |

|--------|----------|---------|

| \[`paysim\_fraud`](paysim\_fraud/) | churn\_analysis | 6.36M-row PaySim run (Kaggle). Wrong target caught at the pre-flight preview and declined; corrected re-run gives baseline ROC-AUC 0.989545, recall 0.476376, no leakage warnings. |

| \[`transaction\_monitoring`](transaction\_monitoring/) | transaction\_monitoring\_review | 2,000-row card sample. 12 rules drafted, approved by SHA-256 at Human Gate 2; Word, PowerPoint, and Excel deliverables. |

| \[`audit\_data\_quality`](audit\_data\_quality/) | data\_quality\_review | 793-row audit-issues register with a planted null pattern, run as an automated workpaper; re-runs are hash-comparable. |

| \[`churn\_analysis`](churn\_analysis/) | churn\_analysis | Planted signal (`churned` iff `tenure\_months < 12`); fixed-seed baseline reaches ROC-AUC 1.0 every run, demonstrating determinism rather than model performance. |

| \[`segment\_comparison`](segment\_comparison/) | segment\_comparison | Statistical inference between segments. |

| \[`universal\_audit`](universal\_audit/) | universal\_audit | Descriptive shape on any table. |



\## Verification



Every package rests on the same claim: `manifest.json` is a hash tree,

and matching hashes prove the files are the ones the run produced. For

the `paysim\_fraud` source, which is not committed, the input's SHA-256

is recorded under `source\_fingerprint`.

