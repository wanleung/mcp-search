import hashlib
import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timezone, timedelta
from elasticsearch import NotFoundError
from cache import cache_get, cache_set

ES_INDEX = "mcp_google_cache"


@pytest.fixture
def mock_es():
    return AsyncMock()


async def test_cache_get_returns_data_on_hit(mock_es):
    cached_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    mock_es.get.return_value = {
        "_source": {
            "key": "test query",
            "data": {"results": [{"title": "Test", "url": "http://test.com", "snippet": "snippet"}]},
            "cached_at": cached_at,
            "ttl_seconds": 86400,
        }
    }
    result = await cache_get(mock_es, "test query")
    assert result == {"results": [{"title": "Test", "url": "http://test.com", "snippet": "snippet"}]}


async def test_cache_get_returns_none_when_expired(mock_es):
    cached_at = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    mock_es.get.return_value = {
        "_source": {
            "key": "test query",
            "data": {"results": []},
            "cached_at": cached_at,
            "ttl_seconds": 86400,
        }
    }
    result = await cache_get(mock_es, "test query")
    assert result is None


async def test_cache_get_returns_none_on_es_error(mock_es):
    mock_es.get.side_effect = Exception("ES unavailable")
    result = await cache_get(mock_es, "test query")
    assert result is None


async def test_cache_set_stores_document(mock_es):
    data = {"results": [{"title": "T", "url": "http://x.com", "snippet": "s"}]}
    await cache_set(mock_es, "test query", data, ttl_seconds=86400)
    mock_es.index.assert_called_once()
    call_kwargs = mock_es.index.call_args.kwargs
    assert call_kwargs["index"] == ES_INDEX
    assert call_kwargs["document"]["key"] == "test query"
    assert call_kwargs["document"]["data"] == data
    assert call_kwargs["document"]["ttl_seconds"] == 86400
    assert "cached_at" in call_kwargs["document"]
    cached_at = datetime.fromisoformat(call_kwargs["document"]["cached_at"])
    assert cached_at.tzinfo is not None  # must be timezone-aware


async def test_cache_set_silently_ignores_es_error(mock_es):
    mock_es.index.side_effect = Exception("ES write failed")
    # Should not raise
    await cache_set(mock_es, "key", {"results": []}, ttl_seconds=86400)


async def test_cache_set_uses_md5_key(mock_es):
    key = "test query"
    expected_id = hashlib.md5(key.encode()).hexdigest()
    await cache_set(mock_es, key, {"results": []}, 86400)
    call_kwargs = mock_es.index.call_args.kwargs
    assert call_kwargs["id"] == expected_id


async def test_cache_get_uses_md5_key(mock_es):
    key = "test query"
    expected_id = hashlib.md5(key.encode()).hexdigest()
    mock_es.get.side_effect = NotFoundError("not found", meta=None, body=None)
    result = await cache_get(mock_es, key)
    assert result is None
    call_kwargs = mock_es.get.call_args.kwargs
    assert call_kwargs["id"] == expected_id
