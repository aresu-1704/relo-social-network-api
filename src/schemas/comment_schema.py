from pydantic import BaseModel, Field, field_validator
from typing import Optional
from ..models import AuthorInfo

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung bình luận")
    
    @field_validator('content')
    @classmethod
    def content_validation(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Nội dung bình luận không được để trống')
        return v.strip()

class CommentPublic(BaseModel):
    id: str
    postId: str
    authorId: str
    authorInfo: AuthorInfo
    content: str
    createdAt: str

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
        json_encoders = {
            'id': lambda v: str(v),
            'authorId': lambda v: str(v),
            'postId': lambda v: str(v),
            'createdAt': lambda v: v.isoformat(),
        }

