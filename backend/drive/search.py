import asyncio
from backend.drive.client import get_drive_service
from backend.cache.ttl_cache import make_cache_key, get_cached, set_cached
import os

FOLDER_ID = os.getenv("FOLDER_ID")
FIELDS = "files(id,name,mimeType,webViewLink,modifiedTime,size,iconLink)"

async def search_drive(query: str) -> dict:
    scopedQuery = f"({query}) and '{FOLDER_ID}' in parents and trashed=false"

    cacheKey = make_cache_key(query=scopedQuery, folderId=FOLDER_ID)

    cached = get_cached(cacheKey)

    if cached:
        return {"files": cached, "from_cache": True, "query": scopedQuery}

    service = get_drive_service()

    result = await asyncio.to_thread(
        lambda: service.files().list(
            q=scopedQuery,
            fields=FIELDS,
            pageSize=15,
            orderBy="modifiedTime desc"
        ).execute()
    )

    files = result.get("files", [])
    set_cached(cacheKey, files)

    return {"files": files, "from_cache": False, "query": scopedQuery}