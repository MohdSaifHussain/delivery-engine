# Security Policy

## Supported versions

| Version | Supported |
|:--------|:----------|
| 1.2.x   | ✅ Yes |
| 1.1.x   | ✅ Yes (security fixes only) |
| 1.0.x   | ⚠️ Critical fixes only |
| < 1.0   | ❌ No |

## Security model

The Delivery Engine is a local analytical workflow tool. It:

- Reads local CSV, XLSX, SQLite, and Parquet files
- Calls the local analystkit and opskit MCP servers
- Writes output packages to local directories
- Does **not** send data to external services
- Does **not** store credentials or personal data
- Does **not** expose network services

The SHA-256 hash chain in `manifest.json` provides tamper-evidence for
output packages. The `declaration.json` (v1.2+) provides a tamper-evident
human accountability record.

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
