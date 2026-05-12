from cachetools  import TTLCache
import hashlib
import json

_cache = TTLCache(maxsize=100, ttl=60)

def make_cache_key(query: str, folderId: str) -> str:
    raw = json.dumps({"q": query, "folder": folderId})
    return hashlib.md5(raw.encode()).hexdigest()

def get_cached(key: str):
    return _cache.get(key)

def set_cached(key: str, value):
    _cache[key] = value