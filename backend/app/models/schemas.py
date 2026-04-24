from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class FileType(str, Enum):
    PDF = "pdf"
    AUDIO = "audio"
    VIDEO = "video"


class TimestampEntry(BaseModel):
    start: float
    end: float
    text: str


class FileDocument(BaseModel):
    file_id: str
    filename: str
    type: FileType
    transcript: Optional[str] = None
    text_content: Optional[str] = None
    chunks: List[str] = []
    timestamps: List[TimestampEntry] = []
    summary: Optional[str] = None
    user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    type: str
    message: str
    summary: Optional[str] = None


class ChatRequest(BaseModel):
    file_id: str
    question: str


class ChatResponse(BaseModel):
    answer: str
    timestamp: Optional[float] = None
    timestamp_text: Optional[str] = None
    sources: List[str] = []


class SummaryResponse(BaseModel):
    file_id: str
    summary: str


class UserCreate(BaseModel):
    username: str
    # email is OPTIONAL — frontend doesn't send it
    email: Optional[str] = None
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class UserInDB(BaseModel):
    username: str
    email: Optional[str] = None
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)