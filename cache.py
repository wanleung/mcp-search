import hashlib
import logging
from datetime import datetime, timezone

from elasticsearch import AsyncElasticsearch, NotFoundError

logger = logging.getLogger(__name__)

INDEX = "mcp_google_cache"


def _make_key(raw: str) -> str:
    """Return the MD5 hex digest of *raw*, used as the Elasticsearch document ID."""
    # MD5 is sufficient for non-security cache key derivation
    return hashlib.md5(raw.encode()).hexdigest()


async def cache_get(es: AsyncElasticsearch, key: str) -> dict | None:
    """Retrieve a cached value from Elasticsearch.

    Parameters
    ----------
    es:
        An async Elasticsearch client instance.
    key:
        The raw cache key (e.g. a search query string).

    Returns
    -------
    dict | None
        The cached ``data`` payload if the entry exists and has not expired,
        otherwise ``None``.
    """
    cache_id = _make_key(key)
    try:
        resp = await es.get(index=INDEX, id=cache_id)
    except NotFoundError:
        return None
    except Exception:
        logger.warning("cache_get: ES error for key %r", key, exc_info=True)
        return None

    source = resp["_source"]
    cached_at = datetime.fromisoformat(source["cached_at"])
    age = (datetime.now(timezone.utc) - cached_at).total_seconds()
    if age > source["ttl_seconds"]:
        return None
    return source["data"]


async def cache_set(es: AsyncElasticsearch, key: str, data: dict, ttl_seconds: int) -> None:
    """Store a value in the Elasticsearch cache.

    Parameters
    ----------
    es:
        An async Elasticsearch client instance.
    key:
        The raw cache key (e.g. a search query string).
    data:
        The payload to cache (must be JSON-serialisable).
    ttl_seconds:
        How long (in seconds) the cached entry is considered valid.
        TTL is enforced at read time by :func:`cache_get`.

    Notes
    -----
    Any Elasticsearch errors are silently swallowed but logged so that cache
    writes never cause the caller to fail.
    """
    cache_id = _make_key(key)
    doc = {
        "key": key,
        "data": data,
        "ttl_seconds": ttl_seconds,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await es.index(index=INDEX, id=cache_id, document=doc)
    except Exception:
        logger.warning("cache_set: failed to write key %r", key, exc_info=True)
