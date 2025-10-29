import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv

# Tải các biến môi trường từ tệp .env
load_dotenv()

# Lấy các giá trị cấu hình JWT từ các biến môi trường
SECRET_KEY = os.getenv("SECRET_KEY")  # Khóa bí mật để ký và xác minh token
ALGORITHM = os.getenv("ALGORITHM")    # Thuật toán mã hóa để sử dụng
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 120))  # Thời gian hết hạn của token truy cập (tính bằng phút)
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 1000)) # Thời gian hết hạn của refresh token (tính bằng ngày)

class TokenData(BaseModel):
    """Mô hình dữ liệu cho payload được giải mã từ token."""
    username: Optional[str] = None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Tạo một token truy cập JWT mới.

    Args:
        data (dict): Dữ liệu (payload) để mã hóa vào token.
        expires_delta (Optional[timedelta]): Thời gian tồn tại của token. Mặc định là 15 phút.

    Returns:
        str: Token JWT đã được mã hóa.
    """
    to_encode = data.copy()
    # Đặt thời gian hết hạn cho token
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    
    # Mã hóa token với khóa bí mật và thuật toán đã định cấu hình
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Tạo một refresh token JWT mới.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Giải mã một token truy cập JWT và trả về payload của nó.

    Args:
        token (str): Token JWT để giải mã.

    Returns:
        Optional[TokenData]: Dữ liệu payload của token nếu giải mã thành công, nếu không thì trả về None.
    """
    try:
        # Cố gắng giải mã token bằng khóa bí mật và thuật toán
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub") # Trích xuất chủ thể (username)
        if username is None:
            return None
        token_data = TokenData(username=username)
    except JWTError:
        # Nếu có lỗi trong quá trình giải mã (ví dụ: hết hạn, không hợp lệ), trả về None
        return None
    return token_data