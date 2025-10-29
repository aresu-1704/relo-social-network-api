from pydantic import BaseModel, EmailStr
from datetime import datetime

class FriendRequestCreate(BaseModel):
    to_user_id: str

class FriendRequestResponse(BaseModel):
    response: str # 'accept' or 'reject'

class UserPublic(BaseModel):
    id: str
    username: str
    email: EmailStr
    displayName: str
    avatarUrl: str | None = ""
    backgroundUrl: str | None = ""
    bio: str | None = ""
    createdAt: str | None = None

class FriendRequestPublic(BaseModel):
    id: str
    fromUserId: str
    toUserId: str
    status: str
    createdAt: datetime

    class Config:
        validate_by_name = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class UserUpdate(BaseModel):
    displayName: str | None = None
    avatarBase64: str | None = None
    backgroundBase64: str | None = None
    bio: str | None = None


class UserSearchResult(BaseModel):
    id: str | None = None
    displayName: str | None = None
    username: str | None = None
    avatarUrl: str | None = None