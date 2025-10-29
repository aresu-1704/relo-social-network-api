from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field


class Notification(Document):
    """
    Model cho thông báo của người dùng
    """
    userId: str = Field(..., description="ID của người dùng nhận thông báo")
    type: str = Field(..., description="Loại thông báo: friend_request_accepted, friend_request_rejected, new_post, etc.")
    title: str = Field(..., description="Tiêu đề thông báo")
    message: str = Field(..., description="Nội dung thông báo")
    metadata: dict = Field(default_factory=dict, description="Thông tin bổ sung (userId của người gửi, postId, etc.)")
    isRead: bool = Field(default=False, description="Đã đọc hay chưa")
    createdAt: datetime = Field(default_factory=datetime.now, description="Thời gian tạo thông báo")
    
    class Settings:
        name = "notifications"
        indexes = [
            [("userId", 1), ("createdAt", -1)],  # Index để query notifications theo userId và sắp xếp theo thời gian
            [("isRead", 1)],  # Index để filter các notification chưa đọc
        ]

