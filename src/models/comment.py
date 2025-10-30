from beanie import Document
from pydantic import Field, BaseModel
from typing import Optional
from datetime import datetime, timedelta
from .post import AuthorInfo

class Comment(Document):
    """
    Đại diện cho một bình luận trong collection 'comments'.
    """
    postId: str = Field(..., description="ID của bài đăng mà bình luận thuộc về.")
    authorId: str = Field(..., description="ID của tác giả bình luận.")
    authorInfo: AuthorInfo = Field(..., description="Thông tin phi chuẩn hóa của tác giả.")
    content: str = Field(..., description="Nội dung văn bản của bình luận.")
    createdAt: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(hours=7), description="Thời điểm bình luận được tạo.")

    class Settings:
        name = "comments"
        indexes = [
            "postId",
            "authorId",
            "createdAt",
        ]

