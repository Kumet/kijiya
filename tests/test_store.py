from unittest.mock import patch

from app.config import settings
from app.services.store import DocStore


async def test_put_and_get_round_trip():
    store = DocStore()
    doc_id = await store.put("<html>ok</html>", "article.html")

    doc = await store.get(doc_id)

    assert doc is not None
    assert doc.html == "<html>ok</html>"
    assert doc.filename == "article.html"


async def test_get_returns_none_for_unknown_id():
    store = DocStore()
    assert await store.get("unknown") is None


async def test_get_returns_none_after_ttl_expires(monkeypatch):
    monkeypatch.setattr(settings, "doc_ttl_seconds", 10)
    store = DocStore()
    clock = [1000.0]

    with patch("app.services.store.time.time", side_effect=lambda: clock[0]):
        doc_id = await store.put("<html>ok</html>", "article.html")
        clock[0] += 20
        doc = await store.get(doc_id)

    assert doc is None


async def test_put_evicts_oldest_when_exceeding_max_docs(monkeypatch):
    monkeypatch.setattr(settings, "max_docs", 2)
    store = DocStore()
    clock = [1000.0]

    with patch("app.services.store.time.time", side_effect=lambda: clock[0]):
        first_id = await store.put("<html>1</html>", "1.html")
        clock[0] += 1
        await store.put("<html>2</html>", "2.html")
        clock[0] += 1
        await store.put("<html>3</html>", "3.html")

        first_doc = await store.get(first_id)

    assert first_doc is None
