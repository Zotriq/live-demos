"""Throwaway PostgreSQL servers that run inside the app, installed with pip.

full()   - PostgreSQL 18 with contrib extensions (pg_trgm…), from postgresql-binaries
vector() - PostgreSQL 16 with pgvector, from pixeltable-pgserver

Each starts once per app process (st.cache_resource) on a Unix socket in a temp
folder and is thrown away when the app restarts. Nothing is persisted.
"""

from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

import streamlit as st

CACHE = Path(tempfile.gettempdir()) / "zotriq-pg"


def _pg18_bin() -> Path:
    import postgresql_binaries

    pkg = Path(postgresql_binaries.__file__).parent
    archive = next(pkg.glob("postgresql-*.tar.gz"))
    target = CACHE / archive.name.removesuffix(".tar.gz")
    if not (target / "bin" / "postgres").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as tar:
            tar.extractall(CACHE, filter="tar")
    return target / "bin"


@st.cache_resource(show_spinner="Starting PostgreSQL…")
def full() -> str:
    """Start PostgreSQL 18 and return a libpq connection string."""
    bindir = _pg18_bin()
    data = Path(tempfile.mkdtemp(prefix="pgdata-"))
    sock = Path(tempfile.mkdtemp(prefix="pgsock-"))
    env = {**os.environ, "LC_ALL": "C"}
    subprocess.run([bindir / "initdb", "-D", data, "-U", "postgres", "--auth=trust", "-E", "UTF8", "--no-instructions"],
                   check=True, capture_output=True, env=env)
    opts = f"-k {sock} -c listen_addresses='' -c shared_buffers=128MB -c max_connections=20 -c fsync=off -c synchronous_commit=off -c full_page_writes=off -c max_parallel_workers_per_gather=0"
    subprocess.run([bindir / "pg_ctl", "-D", data, "-o", opts, "-l", data / "log.txt", "-w", "start"],
                   check=True, capture_output=True, env=env)
    return f"host={sock} user=postgres dbname=postgres"


@st.cache_resource(show_spinner="Starting PostgreSQL with pgvector…")
def vector() -> str:
    """Start PostgreSQL 16 with pgvector and return a libpq connection string."""
    import pixeltable_pgserver

    data = Path(tempfile.mkdtemp(prefix="pgvec-"))
    server = pixeltable_pgserver.get_server(data, cleanup_mode="stop")
    server.psql("CREATE EXTENSION IF NOT EXISTS vector;")
    host = server.get_uri().split("host=")[-1]
    return f"host={host} user=postgres dbname=postgres"
