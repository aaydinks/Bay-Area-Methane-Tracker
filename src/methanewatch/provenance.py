"""Provenance for raw pulls and model runs.

Every download writes ``data/raw/<source>/<pull_id>/manifest.json``; every
model run writes ``data/processed/runs/<run_id>.json``. Published figures cite
the ``run_id``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str, when: datetime | None = None) -> str:
    """Sortable identifier such as ``carbonmapper-20261003T143000Z``."""
    when = when or utcnow()
    return f"{prefix}-{when.strftime('%Y%m%dT%H%M%SZ')}"


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def git_sha(repo: Path | None = None) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


@dataclass
class PullManifest:
    pull_id: str
    source: str
    endpoint: str
    params: dict[str, Any]
    started_at: str
    finished_at: str | None = None
    n_records: int | None = None
    files: dict[str, str] = field(default_factory=dict)  # relative path -> sha256
    git_sha: str | None = None

    @classmethod
    def start(cls, source: str, endpoint: str, params: dict[str, Any]) -> PullManifest:
        now = utcnow()
        return cls(
            pull_id=new_id(source, now),
            source=source,
            endpoint=endpoint,
            params=params,
            started_at=now.isoformat(),
            git_sha=git_sha(),
        )

    def finish(self, pull_dir: Path, files: Iterable[Path], n_records: int) -> Path:
        self.finished_at = utcnow().isoformat()
        self.n_records = n_records
        self.files = {str(p.relative_to(pull_dir)): sha256_file(p) for p in files}
        out = pull_dir / "manifest.json"
        out.write_text(json.dumps(asdict(self), indent=2, sort_keys=True))
        return out


def read_manifests(raw_root: Path) -> list[dict[str, Any]]:
    """Collect every pull manifest under ``raw_root`` (for ``provenance.parquet``)."""
    return [json.loads(p.read_text()) for p in sorted(raw_root.glob("*/*/manifest.json"))]


def git_dirty(repo: Path | None = None) -> bool | None:
    """True when tracked files differ from HEAD, so the run is not reproducible from git_sha."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return bool(out.stdout.strip())


def config_hashes(config_dir: Path | None = None) -> dict[str, str]:
    from methanewatch.config import CONFIG_DIR

    config_dir = config_dir or CONFIG_DIR
    return {p.name: sha256_file(p) for p in sorted(config_dir.glob("*.yaml"))}


def run_manifest(run_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """What a published number depends on: code version, config, library versions."""
    import numpy
    import pymc
    import pytensor

    return {
        "run_id": run_id,
        "created_at": utcnow().isoformat(),
        "git_sha": git_sha(),
        "git_dirty": git_dirty(),
        "config_sha256": config_hashes(),
        "versions": {
            "pymc": pymc.__version__,
            "pytensor": pytensor.__version__,
            "numpy": numpy.__version__,
        },
        **(extra or {}),
    }
