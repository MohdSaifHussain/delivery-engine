# Security Policy

## Supported versions

Only the latest released version is supported. This is a single-maintainer
project with no maintenance branches — fixes land in the next release, not
as backports to an older one.

## Security model

The Delivery Engine is a local analytical workflow tool. It:

- Reads local CSV, XLSX, SQLite, and Parquet files
- Calls the local analystkit and opskit MCP servers
- Writes output packages to local directories
- Does **not** send data to external services
- Does **not** store credentials or personal data
- Does **not** expose network services
- Does **not** collect telemetry. Cross-run local telemetry and opt-in
  crash transmission were both considered and explicitly declined —
  PROJECT_CHARTER.md's v1.2 amendment records the decision and the
  triggers that would revisit it (a bug report that cannot be
  reproduced, a second contributor, or a user with a real operational
  dependency)

The SHA-256 hash chain in `manifest.json` provides tamper-evidence for
output packages. The `declaration.json` (v1.2+) provides a tamper-evident
human accountability record.

When something fails before the executor starts (so no audit log exists
yet), `diagnose.py` writes `delivery-engine-diagnostic.json` — privacy by
construction, not by policy: no usernames, hostnames, absolute paths,
environment variables, or dataset content. Traceback frames are reduced to
`basename.py:LINE in function`; the source file is recorded by extension
only. Nothing is transmitted — the record is written locally, and
attaching it to an issue is your decision.

## Reporting a vulnerability

**Do not open a public GitHub Issue for security vulnerabilities.**

Report security vulnerabilities by:

1. Opening a **private** GitHub Security Advisory at:
   `https://github.com/MohdSaifHussain/delivery-engine/security/advisories/new`

2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if known)

## Response timeline

- **Acknowledgement:** within 48 hours
- **Assessment:** within 7 days
- **Fix (if confirmed):** within 30 days for critical, 90 days for others
- **Disclosure:** coordinated with reporter after fix is released

## Dependency security

- `analystkit` — maintained by the same author
- `duckdb` — Apache 2.0, actively maintained
- `pandas`, `scikit-learn`, `scipy` — standard scientific Python stack

Run `pip audit` to check for known vulnerabilities in installed packages.
