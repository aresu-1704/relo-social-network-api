from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    displayName: str

class UserLogin(BaseModel):
    username: str
    password: str
    device_token: Optional[str] = None

class UserPublic(BaseModel):
    id: str
    username: str
    email: EmailStr
    displayName: str
    avatarUrl: Optional[str] = None
    bio: Optional[str] = None

    class Config:
        from_attributes = True
        # This is to help pydantic convert non-dict objects into pydantic models
        # We need a custom json_encoders for ObjectId
        json_encoders = {
            'id': lambda v: str(v) # Convert ObjectId to string
        }

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class SendOTPRequest(BaseModel):
    identifier: str  # Username hoặc email

class SendOTPResponse(BaseModel):
    message: str
    email: str

class VerifyOTPRequest(BaseModel):
    email: str
    otp_code: str

class VerifyOTPResponse(BaseModel):
    message: str
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str

class ResetPasswordResponse(BaseModel):
    message: str

class ChangeEmailVerifyPasswordRequest(BaseModel):
    user_id: str
    new_email: EmailStr
    password: str

class ChangeEmailVerifyPasswordResponse(BaseModel):
    message: str
    email: str

class UpdateEmailRequest(BaseModel):
    user_id: str
    new_email: EmailStr

class UpdateEmailResponse(BaseModel):
    message: str