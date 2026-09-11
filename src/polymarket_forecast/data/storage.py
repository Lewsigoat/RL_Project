"""Storage abstraction for local files and optional GCS URIs."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import posixpath
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import duckdb
import fsspec
import pandas as pd
from fsspec import AbstractFileSystem


class ResearchStorage:
    """Read and write versioned study artifacts through ``fsspec``.

    ``base_uri`` may be a local directory or an URI such as ``gs://bucket/prefix``.
    GCS support is activated by installing the project's ``gcs`` extra.
    """

    def __init__(self, base_uri: str) -> None:
        self.base_uri = base_uri.rstrip("/")
        self.fs, self.root = fsspec.core.url_to_fs(self.base_uri)
        self.root = self.root.rstrip("/")
        self.fs.makedirs(self.root, exist_ok=True)

    def _path(self, relative: str) -> str:
        clean = relative.lstrip("/")
        return posixpath.join(self.root, clean) if self.root else clean

    def uri(self, relative: str) -> str:
        path = self._path(relative)
        protocol = self.fs.protocol
        if isinstance(protocol, tuple):
            protocol = protocol[0]
        if protocol in {"file", "local"}:
            return str(Path(path).resolve())
        return f"{protocol}://{path}"

    def exists(self, relative: str) -> bool:
        return bool(self.fs.exists(self._path(relative)))

    def makedirs(self, relative: str) -> None:
        self.fs.makedirs(self._path(relative), exist_ok=True)

    def write_bytes(self, relative: str, payload: bytes) -> str:
        """Write bytes and return their SHA-256 digest."""
        path = self._path(relative)
        parent = posixpath.dirname(path)
        if parent:
            self.fs.makedirs(parent, exist_ok=True)
        temporary = f"{path}.tmp"
        with self.fs.open(temporary, "wb") as handle:
            handle.write(payload)
        if self.fs.exists(path):
            self.fs.rm(path)
        self.fs.mv(temporary, path)
        return hashlib.sha256(payload).hexdigest()

    def read_bytes(self, relative: str) -> bytes:
        with self.fs.open(self._path(relative), "rb") as handle:
            return bytes(handle.read())

    def write_json(self, relative: str, payload: Any) -> str:
        data = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=_json_default,
        ).encode("utf-8")
        return self.write_bytes(relative, data)

    def read_json(self, relative: str) -> Any:
        return json.loads(self.read_bytes(relative).decode("utf-8"))

    def write_jsonl_gz(self, relative: str, rows: Iterable[Mapping[str, Any]]) -> str:
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as compressed:
            for row in rows:
                line = json.dumps(
                    dict(row),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=_json_default,
                    separators=(",", ":"),
                )
                compressed.write(line.encode("utf-8") + b"\n")
        return self.write_bytes(relative, buffer.getvalue())

    def read_jsonl_gz(self, relative: str) -> list[dict[str, Any]]:
        payload = self.read_bytes(relative)
        rows: list[dict[str, Any]] = []
        with gzip.GzipFile(fileobj=io.BytesIO(payload), mode="rb") as compressed:
            for line in compressed:
                decoded = json.loads(line)
                if not isinstance(decoded, dict):
                    raise TypeError(f"Expected JSON object in {relative}")
                rows.append({str(key): value for key, value in decoded.items()})
        return rows

    def write_parquet(self, relative: str, frame: pd.DataFrame) -> str:
        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False, compression="zstd")
        return self.write_bytes(relative, buffer.getvalue())

    def read_parquet(self, relative: str) -> pd.DataFrame:
        return pd.read_parquet(io.BytesIO(self.read_bytes(relative)))

    @property
    def is_local(self) -> bool:
        protocol = self.fs.protocol
        if isinstance(protocol, tuple):
            return "file" in protocol or "local" in protocol
        return protocol in {"file", "local"}

    def local_path(self, relative: str) -> Path:
        if not self.is_local:
            raise ValueError("A local path was requested for non-local storage")
        return Path(self._path(relative)).resolve()

    def materialize_duckdb(
        self,
        relative: str,
        tables: Mapping[str, pd.DataFrame],
    ) -> Path:
        """Create a local DuckDB database containing the supplied tables."""
        database = self.local_path(relative)
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(database))
        try:
            for table_name, frame in tables.items():
                if not table_name.replace("_", "").isalnum():
                    raise ValueError(f"Unsafe DuckDB table name: {table_name!r}")
                connection.register("_source_frame", frame)
                connection.execute(
                    f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM _source_frame'
                )
                connection.unregister("_source_frame")
            connection.execute(
                "CREATE OR REPLACE TABLE _study_metadata AS "
                "SELECT current_timestamp AS materialized_at_utc"
            )
        finally:
            connection.close()
        return database


def sha256_file(fs: AbstractFileSystem, path: str, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with fs.open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
