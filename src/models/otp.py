from beanie import Document
from pydantic import Field
from datetime import datetime, timedelta
from typing import Optional

class OTP(Document):
    """
    Đại diện cho mã OTP trong collection 'otps'.
    """
    email: str = Field(..., description="Email của người dùng.")
    otp_code: str = Field(..., description="Mã OTP đã được hash.")
    expires_at: datetime = Field(..., description="Thời gian hết hạn của OTP.")
    is_used: bool = Field(default=False, description="Trạng thái đã sử dụng OTP.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm tạo OTP.")
    
    class Settings:
        name = "otps"
        indexes = [
            "email",
            "expires_at",
        ]

