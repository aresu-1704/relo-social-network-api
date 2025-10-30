# Nhập các thư viện cần thiết
import os
from motor.motor_asyncio import AsyncIOMotorClient # Thư viện bất đồng bộ cho MongoDB
from beanie import init_beanie # ODM (Object-Document Mapper) cho MongoDB
from dotenv import load_dotenv # Để tải các biến môi trường từ file .env
from typing import Type

# Nhập các model từ các file khác
from .user import User
from .conversation import Conversation
from .message import Message
from .post import Post
from .friend_request import FriendRequest
from .otp import OTP
from .notification import Notification
from .comment import Comment

# Danh sách các model Beanie sẽ được khởi tạo
# Thêm tất cả các model của bạn vào đây
DOCUMENT_MODELS: list[Type] = [User, Conversation, Message, Post, FriendRequest, OTP, Notification, Comment]

client = None  # 🔹 client global, dùng 1 lần suốt vòng đời app

async def init_db():
    """
    Khởi tạo kết nối cơ sở dữ liệu và Beanie ODM.
    Đảm bảo chỉ tạo một client duy nhất.
    """
    global client

    # Nếu đã có client, bỏ qua
    if client is not None:
        return client

    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("Không tìm thấy MONGO_URI trong các biến môi trường.")

    # Tạo client duy nhất
    client = AsyncIOMotorClient(mongo_uri)
    database = client.get_database("relo-social-network")

    await init_beanie(database=database, document_models=DOCUMENT_MODELS)

    return client

