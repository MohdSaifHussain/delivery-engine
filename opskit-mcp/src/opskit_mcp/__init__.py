"""opskit-mcp: OpsKit v4.1 exposed as an MCP server with hashed envelopes.

Delivery Engine build-sequence step 6. Pattern: analystkit-mcp applied to
the second kit. Designed, specified, and governed by Mohd Saif Hussain;
implementation AI-directed; every architectural decision human-approved.
"""

from opskit_mcp._vendor import OPSKIT_VERSION, VENDORED_OPSKIT_SHA256

__all__ = ["OPSKIT_VERSION", "VENDORED_OPSKIT_SHA256", "__version__"]
__version__ = "0.1.0"
