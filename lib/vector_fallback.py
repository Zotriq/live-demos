"""pgvector stand-in for hosts where the pip-installed pgvector binary can't load.

The pgvector build that ships with pixeltable-pgserver crashes PostgreSQL on some CPUs
(Streamlit Community Cloud, GitHub runners). For the demos, embeddings are stored as
double precision[] with an exact cosine-distance operator `<=>`, so SQL written for
pgvector (`ORDER BY embedding <=> %s`) runs unchanged. Fine for demo-sized data; a
real deployment uses pgvector with an HNSW index.
"""

from __future__ import annotations

import numpy as np
import psycopg
from psycopg.adapt import Dumper

SQL = """
CREATE OR REPLACE FUNCTION cosine_distance(a double precision[], b double precision[])
RETURNS double precision LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT 1 - sum(x * y) / NULLIF(sqrt(sum(x * x)) * sqrt(sum(y * y)), 0)
  FROM unnest(a, b) AS t(x, y)
$$;
DO $$ BEGIN
  CREATE OPERATOR <=> (LEFTARG = double precision[], RIGHTARG = double precision[], FUNCTION = cosine_distance);
EXCEPTION WHEN duplicate_function THEN NULL; END $$;
"""


def adapt_schema(schema_sql: str, dim: int) -> str:
    """Rewrite a pgvector schema to use float arrays (drops the extension and ANN index lines)."""
    lines = []
    for line in schema_sql.replace("{dim}", str(dim)).splitlines():
        if "CREATE EXTENSION IF NOT EXISTS vector" in line or "USING hnsw" in line or "USING ivfflat" in line:
            continue
        lines.append(line.replace(f"vector({dim})", "double precision[]"))
    return SQL + "\n".join(lines)


class _ArrayDumper(Dumper):
    oid = psycopg.postgres.types["float8"].array_oid

    def dump(self, obj):
        return ("{" + ",".join(repr(float(x)) for x in np.asarray(obj).ravel()) + "}").encode()


def register(conn) -> None:
    """Drop-in for pgvector.psycopg.register_vector: send numpy arrays as float8[]."""
    conn.adapters.register_dumper(np.ndarray, _ArrayDumper)
