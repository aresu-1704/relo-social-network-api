from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from ..models import AuthorInfo, Reaction

class PostCreate(BaseModel):
    content: str = Field(default="", description="Nội dung bài đăng")
    mediaBase64: Optional[List[str]] = Field(default=[], description="Danh sách ảnh dạng base64")
    
    @field_validator('content')
    @classmethod
    def content_validation(cls, v: str) -> str:
        # Allow empty content, but strip whitespace
        if v:
            return v.strip()
        return ""
    
    @field_validator('mediaBase64')
    @classmethod
    def validate_media(cls, v: Optional[List[str]]) -> List[str]:
        if v is None:
            return []
        return v
    
    def model_post_init(self, __context):
        # Ensure at least content or media is provided
        if not self.content and not self.mediaBase64:
            raise ValueError('Vui lòng nhập nội dung hoặc chọn ảnh')

class PostPublic(BaseModel):
    id: str
    authorId: str
    authorInfo: AuthorInfo
    content: str
    mediaUrls: List[str]
    reactions: List[Reaction]
    reactionCounts: dict
    createdAt: str

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
        json_encoders = {
            'id': lambda v: str(v),
            'authorId': lambda v: str(v),
            'createdAt': lambda v: v.isoformat(),
        }

class ReactionCreate(BaseModel):
    reaction_type: str
