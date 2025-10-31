from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.routers import auth_router, user_router, post_router, message_router, notification_router, comment_router
from src import websocket
from src.models import init_db
from src.configs import init_cloudinary

#Khởi tạo kết nối đến Cloudinary
init_cloudinary()

# Khởi tạo app FastAPI với thông tin Swagger UI
app = FastAPI(
    title="Relo Social Network",
    description="Backend mạng xã hội nhắn tin trực tuyến **Relo**.\n\n"
                "Hệ thống hỗ trợ đăng ký, đăng nhập, kết bạn, nhắn tin thời gian thực "
                "và quản lý bài viết cá nhân.",
    version="1.1.311025"
)

# Exception handler cho RequestValidationError (Pydantic validation)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Format lỗi validation cho user-friendly
    errors = exc.errors()
    error_messages = []
    for error in errors:
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error.get("msg", "Validation error")
        error_messages.append(f"{field}: {message}")
    
    detail = "; ".join(error_messages) if error_messages else "Lỗi validation dữ liệu"
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": detail}
    )

# Kết nối với cơ sở dữ liệu khi khởi động
@app.on_event("startup")
async def startup_db_client():
    await init_db()

# Gắn các router
app.include_router(auth_router.router, prefix="/api/auth", tags=["Xác thực"])
app.include_router(user_router.router, prefix="/api/users", tags=["Người dùng"])
app.include_router(post_router.router, prefix="/api/posts", tags=["Bài viết"])
app.include_router(message_router.router, prefix="/api/messages", tags=["Tin nhắn"])
app.include_router(notification_router.router, prefix="/api", tags=["Thông báo"])
app.include_router(comment_router.router, prefix="/api", tags=["Bình luận"])
app.include_router(websocket.router, prefix="/websocket", tags=["Connect real-time"])

@app.get("/")
def read_root():
    return {"message": "Máy chủ đang chạy"}