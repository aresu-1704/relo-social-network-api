from beanie import Document
from pydantic import Field, BaseModel, computed_field
from typing import Optional, List, Dict, Literal
from datetime import datetime, timedelta

class AuthorInfo(BaseModel):
    """Thông tin tác giả được phi chuẩn hóa để hiển thị nhanh."""
    displayName: str
    avatarUrl: Optional[str] = ""

class Reaction(BaseModel):
    """Đại diện cho một phản ứng từ người dùng."""
    userId: str
    type: str

class MediaItem(BaseModel):
    """Media item với URL và publicId để quản lý trên Cloudinary."""
    url: str
    publicId: str
    type: Literal["image", "video", "audio", "file"] = "image"

class Post(Document):
    """
    Đại diện cho một bài đăng trong collection 'posts'.
    """
    authorId: str = Field(..., description="ID của tác giả bài đăng.")
    authorInfo: AuthorInfo = Field(..., description="Thông tin phi chuẩn hóa của tác giả.")
    content: str = Field(..., description="Nội dung văn bản của bài đăng.")
    media: List[MediaItem] = Field(default_factory=list, description="Danh sách media items.")
    reactions: List[Reaction] = Field(default_factory=list, description="Danh sách các phản ứng.")
    reactionCounts: Dict[str, int] = Field(default_factory=dict, description="Số lượng của mỗi loại phản ứng.")
    createdAt: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(hours=7), description="Thời điểm bài đăng được tạo.")

    @property
    def mediaUrls(self) -> List[str]:
        """Trả về danh sách URLs từ media items."""
        return [item.url for item in self.media]

    class Settings:
        name = "posts"
        indexes = [
            "authorId",
            "createdAt",
        ]
        