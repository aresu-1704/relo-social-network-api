from beanie import Document
from pydantic import Field, EmailStr
from typing import Optional, List
from datetime import datetime

class User(Document):
    """
    Đại diện cho một người dùng trong collection 'users'.
    """
    username: str = Field(..., description="Tên đăng nhập duy nhất của người dùng.")
    email: EmailStr = Field(..., description="Địa chỉ email duy nhất của người dùng.")
    hashedPassword: str = Field(..., description="Mật khẩu đã được băm của người dùng.")
    displayName: str = Field(..., description="Tên hiển thị của người dùng.")
    deviceTokens: List[str] = Field(default_factory=list, description="Danh sách device tokens để gửi thông báo đẩy trên nhiều thiết bị.")

    avatarUrl: Optional[str] = Field(default=None, description="URL ảnh đại diện của người dùng.")
    avatarPublicId: Optional[str] = Field(default=None, description="ID công khai của ảnh trên Cloudinary (để xóa hoặc cập nhật ảnh).")
    
    backgroundUrl: Optional[str] = Field(default=None, description="URL ảnh bìa của người dùng.")
    backgroundPublicId: Optional[str] = Field(default=None, description="ID công khai của ảnh trên Cloudinary (để xóa hoặc cập nhật ảnh).")

    bio: Optional[str] = Field(default=None, description="Tiểu sử ngắn của người dùng.")
    friendIds: List[str] = Field(default_factory=list, description="Danh sách ID của bạn bè.")
    blockedUserIds: List[str] = Field(default_factory=list, description="Danh sách ID của người dùng bị chặn.")
    status: Optional[str] = Field(default=None, description="Trạng thái tài khoản: None (mặc định), 'available', 'deleted'.")
    createdAt: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm người dùng được tạo.")
    updatedAt: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm thông tin người dùng được cập nhật lần cuối.")
    
    class Settings:
        name = "users"
        # Thêm các chỉ mục để tối ưu hóa truy vấn
        indexes = [
            "username",
            "email",
        ]
