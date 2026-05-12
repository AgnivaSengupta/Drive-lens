from pydantic import BaseModel
from typing import Optional, List

class ChatRequest(BaseModel):
    session_id: str
    message: str

class FileResult(BaseModel):
    id: str
    name: str
    mimeType: str
    webViewLink: Optional[str]
    modifiedTime: Optional[str]
    size: Optional[str]
    iconLink: Optional[str]

class ChatResponse(BaseModel):
    reply: str
    files: List[FileResult]
    drive_query: Optional[str]
    latency: float      # in ms