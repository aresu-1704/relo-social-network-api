from beanie import Document
from pydantic import Field
from typing import Literal
from datetime import datetime

class FriendRequest(Document):
    """
    Đại diện cho một yêu cầu kết bạn.
    """
    fromUserId: str = Field(..., description="ID của người gửi yêu cầu.")
    toUserId: str = Field(..., description="ID của người nhận yêu cầu.")
    status: Literal['pending', 'accepted', 'rejected'] = Field(default='pending', description="Trạng thái của yêu cầu.")
    createdAt: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm yêu cầu được tạo.")

    class Settings:
        name = "friendRequests"
        indexes = [
            "toUserId",
            "status",
            "createdAt",
        ]
