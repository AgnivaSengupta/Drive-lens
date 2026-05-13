import json
from langchain.tools import tool
from backend.drive.search import search_drive

@tool
async def drive_search_tool(query: str) -> str:
    """
    Search Google Drive using a properly formatted Drive API q parameter.
    Input must be a valid Drive query string containing only file filters.
    The backend automatically searches inside the configured folder and all
    of its subfolders; do not include any parent/folder clause.
    Examples:
      - name contains 'report'
      - mimeType = 'application/pdf' and modifiedTime > '2024-01-01T00:00:00'
      - fullText contains 'budget' and name contains 'Q1'
    Returns a JSON string with the query used and a list of matching files
    (each with id, name, mimeType, webViewLink, modifiedTime, size, iconLink)
    """
    try:
        result = await search_drive(query)
        files = result["files"]

    #     if not files:
    #         return "NO_RESULTS: No files found for that query."

    #     # Return structured text the LLM can parse
    #     output = f"QUERY_USED: {result['query']}\n"
    #     output += f"FOUND: {len(files)} files\n\n"
    #     for f in files:
    #         output += f"- NAME: {f['name']} | TYPE: {f['mimeType']} | "
    #         output += f"MODIFIED: {f.get('modifiedTime','?')} | "
    #         output += f"LINK: {f.get('webViewLink','N/A')}\n"
    #     return output

    # except Exception as e:
    #     # Return error string so LLM can self-correct
    #     return f"HTTP_ERROR: {str(e)}"

        if not files:
            return json.dumps({
                "status": "NO_RESULTS",
                "query": result["query"],
                "count": 0,
                "files": [],
            })

        return json.dumps({
            "status": "OK",
            "query": result["query"],
            "count": len(files),
            "files": files,
        })

    except Exception as e:
        return json.dumps({
            "status": "HTTP_ERROR",
            "error": str(e),
            "query": query,
            "files": [],
        })
