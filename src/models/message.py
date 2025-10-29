from beanie import Document
from pydantic import Field
from typing import Dict
from datetime import datetime

class Message(Document):
    """
    Đại diện cho một tin nhắn trong một cuộc trò chuyện.
    """
    conversationId: str = Field(..., description="ID của cuộc trò chuyện chứa tin nhắn này.")
    senderId: str = Field(..., description="ID của người gửi tin nhắn.")
    content: dict = Field(..., description="Nội dung của tin nhắn, ví dụ: {'type': 'text', 'text': 'Xin chào'}.")
    createdAt: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm tin nhắn được gửi.")

    class Settings:
        name = "messages"
        indexes = [
            "conversationId",
            "createdAt",
        ]
