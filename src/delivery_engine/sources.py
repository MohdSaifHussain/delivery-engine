"""delivery_engine.sources - the single reader.

Step 20. Until now the computational stages (model, stats, math) read
their source with pandas.read_csv while the kit stages read the same
file through AnalystKit's DuckDB loader. Two parsers, one file: a
divergence risk carried openly on the project's register since the
AnalystKit v2.0.x type-boundary bugs, where a mismatch between two
type systems produced 1.5M silent false failures on valid data.

THE SINGLE-READER PRINCIPLE: this module is the ONLY loading path for
the computational stages, and it does not parse anything itself - it
delegates to analystkit.engine.load_source, the very function the
profile gate uses. One reader, one set of type semantics, one place
for a bug to hide. Whatever the profile gate saw, the stages see.

Formats and their rules therefore come from AnalystKit v2.1.0, each
traced to official documentation:

- .csv     - DuckDB read_csv (RFC 4180 quoting, strict_mode=false)
- .parquet - DuckDB read_parquet; the Apache Parquet specification is
             hosted in the apache/parquet-format repository with the
             Thrift IDL authoritative. Nested and semi-structured
             columns (LIST, STRUCT, MAP, UNION, and the VARIANT type
             that went official in February 2026) are a loud refusal
             naming the columns - the engine analyzes tables and says
             so, rather than silently flattening evidence.
- .xlsx    - DuckDB's official excel extension. Its documented
             defaults are disclosed rules: the first sheet is read,
             numeric cells are inferred as DOUBLE. .xls is documented
             as unsupported -> clean refusal with the remedy.
- .db /
  .sqlite  - DuckDB's sqlite extension via ATTACH; exactly one user
             table in v1, otherwise a refusal naming the tables found.

Everything else - hashing, rounding, the findings contract, the
statistics themselves - is untouched by this module. It changes what
the engine can READ, never what it DOES.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd

__all__ = ["SUPPORTED_SUFFIXES", "SourceError", "load_dataframe"]

# The suffixes the single reader accepts. Kept in one place so the
# stages, the planner's source_types, the generator and the runner
# cannot drift apart.
SUPPORTED_SUFFIXES: Final[tuple[str, ...]] = (
    ".csv",
    ".parquet",
    ".xlsx",
    ".db",
    ".sqlite",
    ".sqlite3",
)


class SourceError(Exception):
    """A loading problem, stated cleanly: what, why, what to do."""


def _columns(con: object) -> list[tuple[str, str]]:
    """[(name, duckdb_type)] for the loaded view - the kit's own view
    of the schema, so the reader and the profile gate cannot disagree.
    """
    from analystkit.engine import columns_of

    return columns_of(con)  # type: ignore[arg-type]


def load_dataframe(source: str) -> pd.DataFrame:
    """Loads any supported source into a DataFrame via the ONE reader.

    Raises SourceError (never a raw DuckDB or AnalystKit traceback)
    with the remedy stated, so a bad source is an audited stop in the
    engine's voice rather than a stack trace in a stakeholder's face.
    """
    path = Path(source)
    if not path.exists():
        raise SourceError(
            f"Source not found: {source}. The plan's source must exist "
            f"at execution time."
        )
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise SourceError(
            f"Unsupported source type '{suffix}' ({path.name}). "
            f"Supported: {', '.join(SUPPORTED_SUFFIXES)}. Convert the "
            f"extract and re-run."
        )

    # The single reader: the kit's loader, the same one the profile
    # gate used. Its refusals (nested Parquet, .xls, multi-table
    # SQLite, a renamed CSV) are already loud and specific - they are
    # re-raised as SourceError so the engine's stages speak with one
    # exception vocabulary, with the kit's message preserved verbatim.
    from analystkit.core import AnalystKitError
    from analystkit.engine import load_source

    try:
        con = load_source(path)
    except AnalystKitError as exc:
        raise SourceError(str(exc)) from exc
    try:
        # ── H2 (step-20 hunt): SQLite's dynamic typing lets one column
        # hold integers, text and floats; DuckDB's scanner surfaces
        # such a column as BLOB (raw bytes), and the profile gate
        # reports BLOB too - consistent, but a stage would silently
        # treat bytearrays as categories and profile nonsense. A
        # column the container itself cannot type is a refusal naming
        # the columns and the remedy, never quiet garbage.
        blobs = [name for name, dtype in _columns(con)
                 if dtype.upper().startswith("BLOB")]
        if blobs:
            raise SourceError(
                f"Column(s) {', '.join(blobs)} in {path.name} have no "
                f"single type the source can state (SQLite's dynamic "
                f"typing lets one column mix integers, text and "
                f"floats; the reader surfaces them as raw bytes). "
                f"Give the column one type upstream - e.g. CAST it in "
                f"a view - and re-run. Analyzing untyped bytes would "
                f"be fabrication."
            )
        df = con.execute("SELECT * FROM t").df()
    finally:
        con.close()

    # ── H1 (step-20 hunt): Parquet preserves TIMESTAMP WITH TIME ZONE
    # (an instant), and the reader renders it in UTC. The instant is
    # correct, but day-level findings (gaps, daily counts, trends)
    # would then be computed on UTC calendar days - an IST-midnight
    # event reports the previous day. The engine does not silently
    # re-zone anyone's data; it records that the reading is UTC so the
    # analyst can see it in the findings rather than discover it in a
    # review.
    tz_cols = sorted(
        str(c) for c in df.columns
        if getattr(df[c].dtype, "tz", None) is not None
    )
    if tz_cols:
        df.attrs["timezone_note"] = (
            f"timezone-aware column(s) {', '.join(tz_cols)} are read as "
            f"UTC instants; day-level findings use UTC calendar days"
        )
    return df
