"""Scoped File I/O plugin.

Read/write access is restricted to ``.claude/plans/`` and ``.claude/spec/``. Any path
that resolves outside those roots raises :class:`ScopeViolation`. The project overview
(``settings.project_overview``) is the single read-only exception.

Also provides a per-run read cache so the same resource (e.g. ``CLAUDE.md``, an
existing plan file) is never fetched twice within a single pipeline run.
"""

from __future__ import annotations

from pathlib import Path

from specforge.config import settings


class ScopeViolation(PermissionError):
    """Raised when a path escapes the allowed plans/spec roots."""


def _allowed_roots() -> tuple[Path, ...]:
    return (settings.plans_dir.resolve(), settings.spec_dir.resolve())


def _check_scope(path: Path, *, allow_overview: bool = False) -> Path:
    resolved = Path(path).resolve()
    if allow_overview and resolved == settings.project_overview.resolve():
        return resolved
    if not any(resolved == root or root in resolved.parents for root in _allowed_roots()):
        raise ScopeViolation(f"{resolved} is outside the allowed plans/spec roots")
    return resolved


class RunCache:
    """Content cache keyed by absolute path, lifetime == one pipeline run."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.hits = 0

    def get(self, path: str) -> str | None:
        value = self._store.get(path)
        if value is not None:
            self.hits += 1
        return value

    def put(self, path: str, contents: str) -> None:
        self._store[path] = contents


def read_text(path: str | Path, *, cache: RunCache | None = None, allow_overview: bool = False) -> str:
    resolved = _check_scope(Path(path), allow_overview=allow_overview)
    key = str(resolved)
    if cache is not None and (hit := cache.get(key)) is not None:
        return hit
    contents = resolved.read_text(encoding="utf-8")
    if cache is not None:
        cache.put(key, contents)
    return contents


def write_text(path: str | Path, contents: str, *, cache: RunCache | None = None) -> str:
    resolved = _check_scope(Path(path))
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(contents, encoding="utf-8")
    if cache is not None:
        cache.put(str(resolved), contents)
    return str(resolved)
