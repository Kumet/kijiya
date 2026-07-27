import asyncio
import secrets
import time

from app.config import settings
from app.models import StoredDoc


class DocStore:
    def __init__(self) -> None:
        self._docs: dict[str, StoredDoc] = {}
        self._lock = asyncio.Lock()

    async def put(self, html: str, filename: str) -> str:
        async with self._lock:
            self._purge_expired()

            doc_id = secrets.token_urlsafe(12)
            self._docs[doc_id] = StoredDoc(
                doc_id=doc_id, html=html, filename=filename, created_at=time.time()
            )

            if len(self._docs) > settings.max_docs:
                oldest_id = min(self._docs, key=lambda k: self._docs[k].created_at)
                del self._docs[oldest_id]

            return doc_id

    async def get(self, doc_id: str) -> StoredDoc | None:
        async with self._lock:
            doc = self._docs.get(doc_id)
            if doc is None:
                return None

            if time.time() - doc.created_at > settings.doc_ttl_seconds:
                del self._docs[doc_id]
                return None

            return doc

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [
            doc_id
            for doc_id, doc in self._docs.items()
            if now - doc.created_at > settings.doc_ttl_seconds
        ]
        for doc_id in expired:
            del self._docs[doc_id]


store = DocStore()
