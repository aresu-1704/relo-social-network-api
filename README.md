# Relo Social Network API

Backend API cho mạng xã hội nhắn tin trực tuyến **Relo**. Hệ thống hỗ trợ đăng ký, đăng nhập, kết bạn, nhắn tin thời gian thực, quản lý bài viết cá nhân và thông báo đẩy.

## Tính năng

- **Xác thực người dùng**: Đăng ký, đăng nhập, đăng xuất, quên mật khẩu (OTP), đổi email
- **Quản lý người dùng**: Thông tin cá nhân, ảnh đại diện, ảnh bìa, trạng thái hoạt động
- **Kết bạn**: Gửi/nhận lời mời kết bạn, chấp nhận/từ chối, quản lý danh sách bạn bè, chặn người dùng
- **Nhắn tin real-time**: WebSocket cho tin nhắn tức thời, conversation management
- **Bài viết**: Tạo, sửa, xóa bài viết, thêm hình ảnh (Cloudinary), tìm kiếm
- **Thông báo**: Push notifications qua FCM, thông báo đa thiết bị

## Công nghệ sử dụng

- **Framework**: FastAPI
- **Database**: MongoDB (sử dụng Beanie ODM)
- **Authentication**: JWT tokens (access + refresh)
- **Real-time**: WebSocket
- **Cloud Storage**: Cloudinary (upload ảnh)
- **Notifications**: Firebase Cloud Messaging (FCM)
- **Email**: SMTP cho OTP verification

## Yêu cầu hệ thống

- Python 3.8+
- MongoDB (local hoặc cloud)
- Google Cloud Project (cho Firebase FCM)
- Cloudinary account
- Email SMTP server

## Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/yourusername/Relo-Social-Network-API.git
cd Relo-Social-Network-API
```

### 2. Tạo virtual environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Hoặc sử dụng script có sẵn:

**Windows:**
```bash
setup.bat
```

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Cấu hình môi trường

Tạo file `.env` trong thư mục gốc với nội dung sau:

```env
# MongoDB
MONGO_URI=mongodb://localhost:27017

# JWT Secret (tạo một chuỗi ngẫu nhiên bảo mật)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256

# Cloudinary (có thể giữ nguyên hoặc tạo account mới)
CLOUDINARY_CLOUD_NAME=dxusasr4c
CLOUDINARY_API_KEY=882845991834671
CLOUDINARY_API_SECRET=TBeB6Fca3ozXAyQYTaLcN8DvKY8

# Email SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Firebase FCM
FCM_SERVER_KEY=your-fcm-server-key
FCM_PROJECT_ID=relo-e6b93

# Server
HOST=0.0.0.0
PORT=8000
```

### 5. Chạy ứng dụng

**Windows:**
```bash
run.bat
```

**Hoặc chạy trực tiếp:**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux/Mac:**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Server sẽ chạy tại: `http://localhost:8000`

## API Documentation

### Swagger UI
Truy cập: `http://localhost:8000/docs`

### ReDoc
Truy cập: `http://localhost:8000/redoc`

## API Endpoints

### Xác thực (`/api/auth`)
- `POST /api/auth/register` - Đăng ký người dùng mới
- `POST /api/auth/login` - Đăng nhập
- `POST /api/auth/logout` - Đăng xuất
- `POST /api/auth/refresh` - Làm mới access token
- `POST /api/auth/send-otp` - Gửi mã OTP qua email
- `POST /api/auth/verify-otp` - Xác minh mã OTP
- `POST /api/auth/reset-password` - Đặt lại mật khẩu
- `POST /api/auth/change-email/verify-password` - Xác minh mật khẩu để đổi email
- `POST /api/auth/change-email/update` - Cập nhật email mới

### Người dùng (`/api/users`)
- `GET /api/users/me` - Lấy thông tin người dùng hiện tại
- `PUT /api/users/me` - Cập nhật thông tin cá nhân
- `PUT /api/users/me/avatar` - Cập nhật ảnh đại diện
- `PUT /api/users/me/background` - Cập nhật ảnh bìa
- `GET /api/users/search` - Tìm kiếm người dùng
- `GET /api/users/{user_id}` - Lấy thông tin người dùng theo ID
- `POST /api/users/{user_id}/send-friend-request` - Gửi lời mời kết bạn
- `GET /api/users/friend-requests` - Lấy danh sách lời mời kết bạn
- `POST /api/users/friend-requests/{request_id}/accept` - Chấp nhận lời mời
- `POST /api/users/friend-requests/{request_id}/reject` - Từ chối lời mời
- `GET /api/users/friends` - Lấy danh sách bạn bè
- `DELETE /api/users/friends/{friend_id}` - Xóa bạn
- `POST /api/users/{user_id}/block` - Chặn người dùng
- `DELETE /api/users/{user_id}/block` - Bỏ chặn người dùng
- `GET /api/users/blocked` - Lấy danh sách người dùng đã chặn

### Bài viết (`/api/posts`)
- `POST /api/posts` - Tạo bài viết mới
- `GET /api/posts` - Lấy danh sách bài viết
- `GET /api/posts/{post_id}` - Lấy chi tiết bài viết
- `PUT /api/posts/{post_id}` - Cập nhật bài viết
- `DELETE /api/posts/{post_id}` - Xóa bài viết
- `GET /api/posts/search` - Tìm kiếm bài viết
- `GET /api/posts/user/{user_id}` - Lấy bài viết của người dùng
- `POST /api/posts/{post_id}/like` - Like/Unlike bài viết
- `GET /api/posts/{post_id}/likes` - Lấy danh sách người đã like

### Tin nhắn (`/api/messages`)
- `GET /api/messages/conversations` - Lấy danh sách cuộc trò chuyện
- `GET /api/messages/conversations/{conversation_id}` - Lấy chi tiết cuộc trò chuyện
- `GET /api/messages/conversations/{conversation_id}/messages` - Lấy tin nhắn trong cuộc trò chuyện
- `POST /api/messages/conversations/{conversation_id}/messages` - Gửi tin nhắn

### WebSocket (`/websocket`)
- `WS /websocket/connect?token={jwt_token}` - Kết nối WebSocket cho tin nhắn real-time

### Thông báo (`/api`)
- `GET /api/notifications` - Lấy danh sách thông báo
- `PUT /api/notifications/{notification_id}/read` - Đánh dấu đã đọc
- `GET /api/notifications/unread-count` - Lấy số thông báo chưa đọc

## Authentication

API sử dụng JWT Bearer tokens. Để truy cập các endpoint được bảo vệ:

1. Đăng nhập tại `/api/auth/login` để nhận access token và refresh token
2. Gửi access token trong header: `Authorization: Bearer <access_token>`
3. Khi access token hết hạn, sử dụng refresh token tại `/api/auth/refresh` để lấy access token mới

## Cấu trúc thư mục

```
Relo-Social-Network-API/
├── src/
│   ├── main.py                 # Entry point của ứng dụng
│   ├── security.py             # JWT authentication logic
│   ├── websocket.py            # WebSocket handlers
│   ├── configs/                # Cấu hình (Cloudinary, database)
│   ├── models/                 # Beanie ODM models
│   │   ├── user.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── post.py
│   │   ├── friend_request.py
│   │   ├── notification.py
│   │   ├── otp.py
│   │   └── database.py
│   ├── routers/                # API route handlers
│   │   ├── auth_router.py
│   │   ├── user_router.py
│   │   ├── post_router.py
│   │   ├── message_router.py
│   │   └── notification_router.py
│   ├── schemas/                # Pydantic models cho request/response
│   │   ├── auth_schema.py
│   │   ├── user_schema.py
│   │   ├── post_schema.py
│   │   ├── message_schema.py
│   │   └── block_schema.py
│   ├── services/               # Business logic layer
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── post_service.py
│   │   ├── message_service.py
│   │   ├── notification_service.py
│   │   ├── jwt_service.py
│   │   ├── email_service.py
│   │   └── fcm_service.py
│   └── utils/                  # Utility functions
│       ├── map_to_dict.py
│       └── upload_to_cloudinary.py
├── requirements.txt            # Python dependencies
├── setup.bat                   # Setup script cho Windows
├── setup.sh                    # Setup script cho Linux/Mac
├── run.bat                     # Run script cho Windows
├── relo-api.json              # Firebase service account key
├── LICENSE                     # CC0 1.0 Universal
└── README.md                  # File này
```

## Testing

Xem API documentation tại Swagger UI (`http://localhost:8000/docs`) để test các endpoints trực tiếp.

## License

Creative Commons CC0 1.0 Universal - Xem file [LICENSE](LICENSE) để biết thêm chi tiết.

## Đóng góp

Mọi đóng góp đều được chào đón! Vui lòng tạo Pull Request hoặc mở Issue để thảo luận.

## Tác giả

- **Relo Team**

## Liên hệ

Nếu có câu hỏi hoặc cần hỗ trợ, vui lòng mở một Issue trên GitHub.

---

**Phiên bản**: 1.1.301025
