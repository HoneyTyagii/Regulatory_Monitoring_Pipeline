"""On-disk persistence for raw fetched documents (HTML, PDF, etc.).

Each fetched payload is written verbatim to a content-addressed path and
accompanied by a JSON sidecar holding the :class:`~regmon.models.RawDocument`
metadata. Content addressing (SHA-256 over the raw bytes) gives free
deduplication: re-fetching unchanged content overwrites identical files and is
cheaply detectable via :meth:`RawDocumentStore.is_stored`.

Layout::

    <root>/<jurisdiction>/<source_id>/<byte_hash>.<ext>
    <root>/<jurisdiction>/<source_id>/<byte_hash>.meta.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from regmon.crawler.fetcher import FetchResult
from regmon.logging_config import get_logger
from regmon.models import DocumentFormat, RawDocument, RegulatorySource

log = get_logger(__name__)

_EXTENSIONS: dict[DocumentFormat, str] = {
    DocumentFormat.HTML: "html",
    DocumentFormat.PDF: "pdf",
    DocumentFormat.JSON: "json",
    DocumentFormat.XML: "xml",
    DocumentFormat.TEXT: "txt",
}

#: Formats whose payloads are decoded into ``RawDocument.content`` as text.
_TEXT_FORMATS: frozenset[DocumentFormat] = frozenset(
    {DocumentFormat.HTML, DocumentFormat.XML, DocumentFormat.JSON, DocumentFormat.TEXT}
)


class StoredDocument:
    """Pointer to a persisted raw document and its metadata sidecar."""

    def __init__(self, document: RawDocument, content_path: Path, metadata_path: Path) -> None:
        self.document = document
        self.content_path = content_path
        self.metadata_path = metadata_path


class RawDocumentStore:
    """Persists raw fetched payloads and their metadata to the filesystem."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def byte_hash(content: bytes) -> str:
        """SHA-256 hex digest of raw bytes, used for addressing and dedup."""
        return hashlib.sha256(content).hexdigest()

    def _dir_for(self, jurisdiction: str, source_id: str) -> Path:
        return self._root / jurisdiction / source_id

    def _paths(
        self, source: RegulatorySource, digest: str, doc_format: DocumentFormat
    ) -> tuple[Path, Path]:
        directory = self._dir_for(source.jurisdiction.value, source.id)
        ext = _EXTENSIONS[doc_format]
        return directory / f"{digest}.{ext}", directory / f"{digest}.meta.json"

    def is_stored(
        self, source: RegulatorySource, content: bytes, doc_format: DocumentFormat
    ) -> bool:
        """Return whether identical content for this source is already on disk."""
        content_path, _ = self._paths(source, self.byte_hash(content), doc_format)
        return content_path.is_file()

    def save(self, source: RegulatorySource, result: FetchResult) -> StoredDocument:
        """Persist a fetch result and return a :class:`StoredDocument`.

        The raw bytes are written to disk regardless of format. Text-based
        formats are also decoded into ``RawDocument.content``; binary formats
        (e.g. PDF) keep ``content`` empty here and are extracted by the parser
        stage downstream.
        """
        doc_format = result.detect_format()
        digest = self.byte_hash(result.content)
        content_path, metadata_path = self._paths(source, digest, doc_format)
        content_path.parent.mkdir(parents=True, exist_ok=True)

        content_path.write_bytes(result.content)

        text_content = result.text() if doc_format in _TEXT_FORMATS else ""
        document = RawDocument(
            source_id=source.id,
            jurisdiction=source.jurisdiction,
            url=result.url,
            content=text_content,
            content_format=doc_format,
            http_status=result.status_code,
            fetched_at=result.fetched_at,
            metadata={
                "byte_hash": digest,
                "byte_size": len(result.content),
                "content_type": result.content_type,
                "content_path": str(content_path),
                "elapsed_seconds": result.elapsed_seconds,
            },
        )

        metadata_path.write_text(
            json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        log.info(
            "crawler.stored",
            source_id=source.id,
            jurisdiction=source.jurisdiction.value,
            format=doc_format.value,
            byte_size=len(result.content),
            path=str(content_path),
        )
        return StoredDocument(document, content_path, metadata_path)


__all__ = ["RawDocumentStore", "StoredDocument"]
