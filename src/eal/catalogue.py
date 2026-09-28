"""Persistent developer catalogue of EAL sources and their stored run history.

An entry has a stable developer name and workspace path. Each validated file
revision is retained by its exact source digest. Collection and assessment
records remain owned by RunStore; this catalogue indexes their identities and
never turns a historical result into a fresh observation.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from .evaluator import canonical_digest
from .parser import MAX_SOURCE_BYTES, parse
from .runtime import ReasoningService, bounded_path
from .store import utc_now


_ENTRY_ID = re.compile(r"[A-Za-z_][A-Za-z_0-9.-]{0,127}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MAX_CONTEXT_BYTES = 8192
_MAX_CLAIMS = 256
_MAX_TREE_FILES = 512
_MAX_TREE_ENTRIES = 8192
_MAX_TREE_DEPTH = 16


def _json(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
        encoded.encode("utf-8")
        return encoded
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Catalogue values must be finite UTF-8 JSON") from exc


def _limit(value: int) -> int:
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError("limit must be an integer from 1 through 100")
    return value


class WorkspaceKnowledgeCatalogue:
    """Named workspace sources with immutable revisions and indexed run lookup."""

    def __init__(self, service: ReasoningService):
        self.service = service
        self.workspace = service.workspace
        self.store = service.store
        with self.store._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS catalogue_entries ("
                "entry_id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, label TEXT NOT NULL, "
                "context_json TEXT NOT NULL, selected_claims_json TEXT, "
                "current_digest TEXT NOT NULL, current_method_fingerprint TEXT NOT NULL, "
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS catalogue_revisions ("
                "entry_id TEXT NOT NULL, source_digest TEXT NOT NULL, source TEXT NOT NULL, "
                "method_registry_fingerprint TEXT NOT NULL, claims_json TEXT NOT NULL, "
                "claim_metadata_json TEXT NOT NULL, registered_at TEXT NOT NULL, "
                "PRIMARY KEY(entry_id, source_digest, method_registry_fingerprint), "
                "FOREIGN KEY(entry_id) REFERENCES catalogue_entries(entry_id))"
            )
            # Existing collections and assessments become discoverable without
            # copying potentially large observation values into catalogue rows.
            connection.execute(
                "CREATE INDEX IF NOT EXISTS catalogue_run_source ON records "
                "(kind, json_extract(payload, '$.source_digest'))"
            )

    def _normal_path(self, path: str) -> str:
        if not isinstance(path, str) or not path or Path(path).is_absolute() or not path.endswith(".eal"):
            raise ValueError("path must be a workspace-relative .eal file")
        resolved = bounded_path(self.workspace, path)
        return resolved.relative_to(self.workspace).as_posix()

    def _read_source(self, relative_path: str) -> str:
        path = bounded_path(self.workspace, relative_path)
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("Registered source must be a regular EAL file")
        with path.open("rb") as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES:
            raise ValueError("Registered source exceeds the EAL source limit")
        try:
            return data.decode("utf-8")
        except UnicodeError as exc:
            raise ValueError("Registered source must be UTF-8") from exc

    @staticmethod
    def _metadata(source: str, selected_claims: tuple[str, ...] | None) -> tuple[str, dict[str, dict]]:
        program = parse(source)
        names = tuple(program.claims) if selected_claims is None else selected_claims
        missing = set(names) - set(program.claims)
        if missing:
            raise ValueError(f"Selected claims are absent from the source: {', '.join(sorted(missing))}")
        if not names or len(names) > _MAX_CLAIMS:
            raise ValueError(f"Register one to {_MAX_CLAIMS} selected claims")
        details = {name: {"statement": program.claims[name].statement,
                          "environment": program.claims[name].environment} for name in names}
        return program.source_digest, details

    def _validate_revision(self, source: str, selected_claims: tuple[str, ...] | None) -> tuple[str, str, dict[str, dict]]:
        validation = self.service.validate(source)
        if not validation["valid"]:
            raise ValueError("Registered source failed EAL validation: " +
                             "; ".join(item["message"] for item in validation["diagnostics"][:5]))
        source_digest, metadata = self._metadata(source, selected_claims)
        if source_digest != validation["source_digest"]:
            raise ValueError("Source changed during validation")
        return source_digest, validation["method_registry_fingerprint"], metadata

    def register(self, path: str, *, entry_id: str | None = None,
                 context: dict[str, Any] | None = None,
                 claims: list[str] | tuple[str, ...] | None = None,
                 label: str | None = None) -> dict[str, Any]:
        """Register a trusted path; repeated calls retain its stable entry ID."""
        relative = self._normal_path(path)
        identifier = relative if entry_id is None else entry_id
        if not isinstance(identifier, str) or not identifier or len(identifier) > 256:
            raise ValueError("entry_id must be a bounded nonempty string")
        try:
            identifier.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("entry_id must be valid UTF-8") from exc
        if entry_id is not None and not _ENTRY_ID.fullmatch(entry_id):
            raise ValueError("Explicit entry_id must be a simple developer name")
        if label is None:
            label = Path(relative).stem
        if not isinstance(label, str) or not 1 <= len(label) <= 128 or not label.strip():
            raise ValueError("label must contain one to 128 characters")
        try:
            label.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("label must be valid UTF-8") from exc
        if context is None:
            context = {}
        if not isinstance(context, dict):
            raise ValueError("context must be a JSON object")
        context_json = _json(context)
        if len(context_json.encode("utf-8")) > _MAX_CONTEXT_BYTES:
            raise ValueError("context exceeds 8192 UTF-8 bytes")
        if claims is not None:
            if (not isinstance(claims, (list, tuple)) or not claims
                    or len(claims) > _MAX_CLAIMS or any(not isinstance(name, str) for name in claims)
                    or len(set(claims)) != len(claims)):
                raise ValueError("claims must contain unique claim identifiers")
            selected = tuple(claims)
        else:
            selected = None
        selected_json = None if selected is None else _json(selected)
        source = self._read_source(relative)
        digest, method_fingerprint, metadata = self._validate_revision(source, selected)
        now = utc_now()
        with self.store._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT path, label, context_json, selected_claims_json FROM catalogue_entries "
                "WHERE entry_id = ?", (identifier,)
            ).fetchone()
            expected = (relative, label, context_json, selected_json)
            if row is not None and row != expected:
                raise ValueError("Registered entry metadata differs; use another developer entry_id")
            path_owner = connection.execute(
                "SELECT entry_id FROM catalogue_entries WHERE path = ?", (relative,)
            ).fetchone()
            if path_owner is not None and path_owner[0] != identifier:
                raise ValueError("Source path is already registered under another entry_id")
            if row is None:
                connection.execute(
                    "INSERT INTO catalogue_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (identifier, relative, label, context_json, selected_json,
                     digest, method_fingerprint, now, now),
                )
            else:
                connection.execute(
                    "UPDATE catalogue_entries SET current_digest = ?, "
                    "current_method_fingerprint = ?, updated_at = ? "
                    "WHERE entry_id = ? AND (current_digest != ? OR current_method_fingerprint != ?)",
                    (digest, method_fingerprint, now, identifier, digest, method_fingerprint),
                )
            connection.execute(
                "INSERT OR IGNORE INTO catalogue_revisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (identifier, digest, source, method_fingerprint,
                 _json(tuple(metadata)), _json(metadata), now),
            )
        return self.get(identifier, include_source=False, refresh=False)

    def register_tree(self, directory: str = ".", *, context: dict[str, Any] | None = None,
                      limit: int = _MAX_TREE_FILES) -> dict[str, Any]:
        """Discover bounded workspace files and report every rejected source."""
        if type(limit) is not int or not 1 <= limit <= _MAX_TREE_FILES:
            raise ValueError(f"limit must be an integer from 1 through {_MAX_TREE_FILES}")
        if not isinstance(directory, str) or Path(directory).is_absolute():
            raise ValueError("directory must be workspace-relative")
        root = bounded_path(self.workspace, directory)
        if not root.is_dir():
            raise ValueError("directory must resolve to a workspace directory")
        paths = []
        visited = 0

        def traversal_error(error: OSError) -> None:
            raise error

        for base, directories, files in os.walk(root, followlinks=False,
                                                 onerror=traversal_error):
            directories.sort()
            files.sort()
            visited += len(directories) + len(files)
            if visited > _MAX_TREE_ENTRIES:
                raise ValueError("Directory exceeds the discovery scan limit")
            if len(Path(base).relative_to(root).parts) >= _MAX_TREE_DEPTH and directories:
                raise ValueError("Directory exceeds the discovery depth limit")
            for filename in files:
                if filename.endswith(".eal"):
                    paths.append(Path(base) / filename)
                    if len(paths) > limit:
                        raise ValueError("Directory contains more EAL files than the discovery limit")
        registered, rejected = [], []
        for path in sorted(paths):
            relative = path.relative_to(self.workspace).as_posix()
            try:
                registered.append(self.register(relative, context=context))
            except (OSError, ValueError) as exc:
                rejected.append({"path": relative, "reason": str(exc)})
        return {"registered": registered, "rejected": rejected}

    def _entry(self, entry_id: str, source_digest: str | None = None,
               *, method_fingerprint: str | None = None,
               include_source: bool = False) -> dict[str, Any]:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT e.entry_id, e.path, e.label, e.context_json, e.selected_claims_json, "
                "e.current_digest, e.current_method_fingerprint, "
                "r.source_digest, r.source, r.method_registry_fingerprint, "
                "r.claims_json, r.claim_metadata_json, r.registered_at "
                "FROM catalogue_entries e JOIN catalogue_revisions r "
                "ON r.entry_id = e.entry_id AND r.source_digest = COALESCE(?, e.current_digest) "
                "WHERE e.entry_id = ? AND (? IS NULL OR r.method_registry_fingerprint = ?) "
                "ORDER BY (r.source_digest = e.current_digest AND "
                "r.method_registry_fingerprint = e.current_method_fingerprint) DESC, "
                "r.registered_at DESC LIMIT 1",
                (source_digest, entry_id, method_fingerprint, method_fingerprint),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown catalogue entry or source revision {entry_id!r}")
        (identifier, path, label, context_json, selected_claims_json,
         current_digest, current_method_fingerprint, digest, source,
         method_fingerprint, claims_json, metadata_json, registered_at) = row
        result = {"entry_id": identifier, "path": path, "label": label,
                  "source_digest": digest,
                  "current": digest == current_digest and method_fingerprint == current_method_fingerprint,
                  "method_registry_fingerprint": method_fingerprint,
                  "context": json.loads(context_json), "claims": json.loads(claims_json),
                  "selected_claims": None if selected_claims_json is None else json.loads(selected_claims_json),
                  "claim_metadata": json.loads(metadata_json), "registered_at": registered_at}
        if include_source:
            result["source"] = source
        return result

    def get(self, entry_id: str, *, include_source: bool = False,
            refresh: bool = True) -> dict[str, Any]:
        """Return the latest validated revision, incorporating a changed file."""
        if refresh:
            current = self._entry(entry_id)
            self.register(current["path"], entry_id=entry_id, context=current["context"],
                          claims=current["selected_claims"], label=current["label"])
        return self._entry(entry_id, include_source=include_source)

    def get_revision(self, entry_id: str, source_digest: str, *,
                     method_registry_fingerprint: str | None = None,
                     include_source: bool = False) -> dict[str, Any]:
        if not isinstance(source_digest, str) or _DIGEST.fullmatch(source_digest) is None:
            raise ValueError("source_digest must be a lowercase SHA-256 digest")
        if (method_registry_fingerprint is not None and
                (not isinstance(method_registry_fingerprint, str) or
                 _DIGEST.fullmatch(method_registry_fingerprint) is None)):
            raise ValueError("method_registry_fingerprint must be a lowercase SHA-256 digest")
        return self._entry(entry_id, source_digest,
                           method_fingerprint=method_registry_fingerprint,
                           include_source=include_source)

    def revisions(self, entry_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """List immutable source and method identities, including old revisions."""
        _limit(limit)
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT current_digest, current_method_fingerprint FROM catalogue_entries "
                "WHERE entry_id = ?", (entry_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown catalogue entry {entry_id!r}")
            revisions = connection.execute(
                "SELECT source_digest, method_registry_fingerprint, registered_at, claims_json "
                "FROM catalogue_revisions WHERE entry_id = ? "
                "ORDER BY registered_at DESC, source_digest LIMIT ?", (entry_id, limit),
            ).fetchall()
        return [{"source_digest": digest, "method_registry_fingerprint": fingerprint,
                 "registered_at": registered_at, "claims": json.loads(claims),
                 "current": (digest, fingerprint) == row}
                for digest, fingerprint, registered_at, claims in revisions]

    def list(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        _limit(limit)
        if type(offset) is not int or not 0 <= offset <= 10_000:
            raise ValueError("offset must be an integer from 0 through 10000")
        with self.store._connect() as connection:
            identifiers = [row[0] for row in connection.execute(
                "SELECT entry_id FROM catalogue_entries ORDER BY path LIMIT ? OFFSET ?",
                (limit, offset),
            )]
        return [self._entry(identifier) for identifier in identifiers]

    def find(self, query: str | None = None, *, claim: str | None = None,
             context: dict[str, Any] | None = None, path: str | None = None,
             limit: int = 50) -> list[dict[str, Any]]:
        """Advisory metadata search; execution still requires an exact entry ID."""
        _limit(limit)
        if query is not None and (not isinstance(query, str) or len(query) > 256):
            raise ValueError("query must be at most 256 characters")
        if claim is not None and not isinstance(claim, str):
            raise ValueError("claim must be a string")
        if path is not None and not isinstance(path, str):
            raise ValueError("path must be a string")
        context_json = None
        if context is not None:
            if not isinstance(context, dict):
                raise ValueError("context must be a JSON object")
            context_json = _json(context)
        with self.store._connect() as connection:
            rows = connection.execute(
                "SELECT e.entry_id FROM catalogue_entries e JOIN catalogue_revisions r "
                "ON r.entry_id = e.entry_id AND r.source_digest = e.current_digest "
                "AND r.method_registry_fingerprint = e.current_method_fingerprint "
                "WHERE (? IS NULL OR instr(lower(e.path || ' ' || e.label || ' ' || "
                "r.claim_metadata_json), lower(?)) > 0) "
                "AND (? IS NULL OR EXISTS (SELECT 1 FROM json_each(r.claims_json) WHERE value = ?)) "
                "AND (? IS NULL OR e.context_json = ?) AND (? IS NULL OR e.path = ?) "
                "ORDER BY e.path LIMIT ?",
                (query, query, claim, claim, context_json, context_json, path, path, limit),
            ).fetchall()
        return [self._entry(row[0]) for row in rows]

    def runs(self, entry_id: str, *, source_digest: str | None = None,
             limit: int = 50) -> dict[str, Any]:
        """Find exact-source, exact-context historical runs without replaying them."""
        _limit(limit)
        entry = (self.get(entry_id) if source_digest is None else
                 self.get_revision(entry_id, source_digest))
        digest = entry["source_digest"]
        context_json = _json(entry["context"])
        context_fingerprint = canonical_digest(entry["context"])
        with self.store._connect() as connection:
            collections = connection.execute(
                "SELECT id, created_at, payload FROM records "
                "WHERE kind = 'collection' AND json_extract(payload, '$.source_digest') = ? "
                "AND json_extract(payload, '$.context') = ? ORDER BY rowid DESC LIMIT ?",
                (digest, context_json, limit),
            ).fetchall()
            assessments = connection.execute(
                "SELECT id, created_at, payload FROM records "
                "WHERE kind = 'assessment' AND json_extract(payload, '$.source_digest') = ? "
                "AND json_extract(payload, '$.context_fingerprint') = ? "
                "ORDER BY rowid DESC LIMIT ?",
                (digest, context_fingerprint, limit),
            ).fetchall()
        return {"entry_id": entry_id, "source_digest": digest,
                "collections": [{"collection_id": record_id, "created_at": created_at,
                                 "record_count": len(json.loads(payload).get("records", {}))}
                                for record_id, created_at, payload in collections],
                "assessments": [{"assessment_id": record_id,
                                 "collection_id": item.get("collection_id"),
                                 "created_at": created_at, "assessed_at": item.get("assessed_at"),
                                 "method_registry_fingerprint": item.get("method_registry_fingerprint"),
                                 "claim_statuses": {name: value.get("status") for name, value in
                                                    item.get("claims", {}).items() if name in entry["claims"]}}
                                for record_id, created_at, payload in assessments
                                for item in (json.loads(payload),)]}
