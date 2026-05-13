import asyncio
import os
import warnings

from dotenv import load_dotenv

from backend.cache.ttl_cache import get_cached, make_cache_key, set_cached
from backend.drive.client import get_drive_service


load_dotenv()

FOLDER_ID = os.getenv("FOLDER_ID")
if not FOLDER_ID:
    warnings.warn(
        "FOLDER_ID environment variable is not set. "
        "Drive searches will scan all of Drive instead of a scoped folder.",
        RuntimeWarning,
        stacklevel=1,
    )

FILE_FIELDS = "nextPageToken, files(id,name,mimeType,webViewLink,modifiedTime,size,iconLink)"
FOLDER_FIELDS = "nextPageToken, files(id,name,mimeType)"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
MAX_RESULTS = 100


def _normalize_query(query: str) -> str:
    query = (query or "").strip()
    if query in {"", "()"}:
        return f"mimeType != '{FOLDER_MIME_TYPE}'"
    return query


def _parents_query(folder_ids: list[str]) -> str:
    return " or ".join(f"'{folder_id}' in parents" for folder_id in folder_ids)


def _list_all_pages(service, query: str, fields: str, page_size: int = 100) -> list[dict]:
    files: list[dict] = []
    page_token = None

    while True:
        result = (
            service.files()
            .list(
                q=query,
                fields=fields,
                pageSize=page_size,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return files


def _descendant_folder_ids(service, root_folder_id: str) -> list[str]:
    folder_ids = [root_folder_id]
    queue = [root_folder_id]

    while queue:
        parent_id = queue.pop(0)
        query = (
            f"'{parent_id}' in parents and "
            f"mimeType = '{FOLDER_MIME_TYPE}' and trashed=false"
        )
        child_folders = _list_all_pages(service, query, FOLDER_FIELDS)
        child_ids = [folder["id"] for folder in child_folders if folder.get("id")]
        folder_ids.extend(child_ids)
        queue.extend(child_ids)

    return folder_ids


def _run_drive_search(query: str) -> dict:
    normalized_query = _normalize_query(query)
    service = get_drive_service()

    if FOLDER_ID:
        folder_ids = _descendant_folder_ids(service, FOLDER_ID)
        parent_clause = _parents_query(folder_ids)
        scoped_query = f"({normalized_query}) and ({parent_clause}) and trashed=false"
    else:
        scoped_query = f"({normalized_query}) and trashed=false"

    files = _list_all_pages(service, scoped_query, FILE_FIELDS)
    files = sorted(files, key=lambda f: f.get("modifiedTime", ""), reverse=True)

    return {"files": files[:MAX_RESULTS], "query": scoped_query}


async def search_drive(query: str) -> dict:
    normalized_query = _normalize_query(query)
    cacheKey = make_cache_key(query=normalized_query, folderId=FOLDER_ID or "")

    cached = get_cached(cacheKey)

    if cached:
        return {**cached, "from_cache": True}

    result = await asyncio.to_thread(_run_drive_search, normalized_query)
    set_cached(cacheKey, result)

    return {**result, "from_cache": False}
