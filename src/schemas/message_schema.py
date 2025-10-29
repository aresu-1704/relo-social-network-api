from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from .user_schema import UserPublic
from ..models import ParticipantInfo

class MessageCreate(BaseModel):
    content: dict

class ConversationCreate(BaseModel):
    participant_ids: List[str]
    is_group: bool = False
    name: Optional[str] = None

# Schema for simplified message response
class SimpleMessagePublic(BaseModel):
    id: str
    senderId: str
    avatarUrl: Optional[str]
    content: Dict
    createdAt: datetime

class MessagePublic(BaseModel):
    id: str
    conversationId: str
    senderId: str
    content: dict
    createdAt: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class LastMessagePublic(BaseModel):
    content: dict
    senderId: str
    createdAt: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class ConversationPublic(BaseModel):
    id: str
    participants: List[ParticipantInfo]
    lastMessage: Optional[LastMessagePublic]
    updatedAt: datetime
    seenIds: List[str] = []
    isGroup: bool = False
    name: str | None = None
    avatarUrl: str | None = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class ConversationWithParticipants(BaseModel):
    id: str
    participantsInfo: List[ParticipantInfo]
    participants: List[UserPublic]
    lastMessage: Optional[LastMessagePublic]
    updatedAt: datetime
    seenIds: List[str] = []
    isGroup: bool = False
    name: str | None = None
    avatarUrl: str | None = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
