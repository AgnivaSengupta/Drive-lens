from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List

class ChatRequest(BaseModel):
    session_id: str
    user_id: str
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
    latency_ms: float

class Session(BaseModel):
    session_id: str
    user_id: str
    title: str
    created_at: str

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"
    
