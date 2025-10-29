import os
import json
import base64
import httpx
from typing import List, Optional, Dict
from pathlib import Path
from google.oauth2 import service_account
import google.auth.transport.requests
from dotenv import load_dotenv
from ..models import User

# Load environment variables
load_dotenv()


class FCMService:
    """Service để gửi push notification qua Firebase Cloud Messaging"""
    
    FCM_SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']
    _credentials = None
    _access_token = None
    
    @staticmethod
    def _load_service_account() -> Optional[service_account.Credentials]:
        """Load Firebase service account credentials từ environment variables hoặc file JSON
        
        Thứ tự ưu tiên:
        1. FIREBASE_CREDENTIALS_BASE64 (base64-encoded JSON) - cho Vercel deployment
        2. FIREBASE_* individual env vars - cho local development với .env
        3. GOOGLE_APPLICATION_CREDENTIALS hoặc relo-api.json - fallback
        """
        try:
            # Ưu tiên 1: Đọc từ base64-encoded JSON (cho Vercel)
            firebase_creds_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
            if firebase_creds_base64:
                try:
                    # Decode base64
                    decoded_bytes = base64.b64decode(firebase_creds_base64)
                    service_account_info = json.loads(decoded_bytes.decode('utf-8'))
                    
                    credentials = service_account.Credentials.from_service_account_info(
                        service_account_info,
                        scopes=FCMService.FCM_SCOPES
                    )
                    return credentials
                except Exception as e:
                    print(f"⚠️ Error decoding FIREBASE_CREDENTIALS_BASE64: {e}")
                    # Continue to next option
            
            # Ưu tiên 2: Đọc từ các biến môi trường riêng lẻ (cho local .env)
            project_id = os.getenv("FIREBASE_PROJECT_ID")
            private_key = os.getenv("FIREBASE_PRIVATE_KEY")
            client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
            
            if project_id and private_key and client_email:
                # Tạo service account info từ env vars
                # Xử lý private_key: loại bỏ dấu ngoặc kép nếu có và thay \n thành newline thực sự
                clean_private_key = private_key.strip('"').replace('\\n', '\n')
                
                service_account_info = {
                    "type": os.getenv("FIREBASE_TYPE", "service_account"),
                    "project_id": project_id,
                    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID", ""),
                    "private_key": clean_private_key,
                    "client_email": client_email,
                    "client_id": os.getenv("FIREBASE_CLIENT_ID", ""),
                    "auth_uri": os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                    "token_uri": os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"),
                    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL", ""),
                    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN", "googleapis.com")
                }
                
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=FCMService.FCM_SCOPES
                )
                return credentials
            
            # Fallback: Tìm file service account JSON
            service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            
            if not service_account_path:
                # Fallback: tìm file relo-api.json trong thư mục api
                current_dir = Path(__file__).parent.parent.parent.parent
                service_account_path = current_dir / "relo-api.json"
                if not service_account_path.exists():
                    # Thử tìm trong thư mục hiện tại
                    service_account_path = Path("relo-api.json")
            
            if service_account_path and Path(service_account_path).exists():
                credentials = service_account.Credentials.from_service_account_file(
                    str(service_account_path),
                    scopes=FCMService.FCM_SCOPES
                )
                return credentials
            else:
                print("⚠️ Firebase service account credentials not found in .env or JSON file")
                return None
        except Exception as e:
            print(f"⚠️ Error loading Firebase service account: {e}")
            return None
    
    @staticmethod
    async def _get_access_token() -> Optional[str]:
        """
        Lấy access token từ Firebase service account (OAuth2).
        Token được cache và refresh tự động khi hết hạn.
        """
        try:
            # Load credentials nếu chưa có
            if not FCMService._credentials:
                FCMService._credentials = FCMService._load_service_account()
                if not FCMService._credentials:
                    return None
            
            # Refresh token nếu cần
            request = google.auth.transport.requests.Request()
            FCMService._credentials.refresh(request)
            
            return FCMService._credentials.token
        except Exception as e:
            print(f"⚠️ Error getting FCM access token: {e}")
            return None
    
    @staticmethod
    async def send_notification(
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None,
        conversation_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None,
        message_type: Optional[str] = None,
        sender_avatar: Optional[str] = None,
        image_url: Optional[str] = None,
        conversation_name: Optional[str] = None,
        is_group: bool = False
    ) -> List[str]:
        """
        Gửi push notification tới danh sách device tokens.
        
        Args:
            device_tokens: Danh sách FCM device tokens
            title: Tiêu đề notification
            body: Nội dung notification
            data: Data payload cho notification
            conversation_id: ID của conversation (để reply)
            sender_id: ID của người gửi
            sender_name: Tên người gửi
            message_type: Loại message (text, image, etc.)
        
        Returns:
            List các device token đã gửi thành công
        """
        if not device_tokens:
            return []
        
        access_token = await FCMService._get_access_token()
        if not access_token:
            print("⚠️ FCM access token not available, skipping push notification")
            return []
        
        # Lấy project_id từ credentials
        project_id = None
        if FCMService._credentials:
            project_id = FCMService._credentials.project_id
        
        if not project_id:
            print("⚠️ FCM project_id not available")
            return []
        
        # Sử dụng FCM HTTP v1 API với OAuth2 token
        fcm_url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        successful_tokens = []
        failed_tokens = []
        
        # Gửi từng notification (có thể batch sau)
        for token in device_tokens:
            # FCM v1 API format
            # Lưu ý: Reply actions được xử lý ở client-side (local notification)
            # FCM v1 không hỗ trợ actions trong payload
            message_payload = {
                "message": {
                    "token": token,
                    "notification": {
                        "title": title,
                        "body": body
                    },
                    "data": {
                        "type": "message",
                        "conversation_id": conversation_id or "",
                        "sender_id": sender_id or "",
                        "sender_name": sender_name or "",
                        "sender_avatar": str(sender_avatar) if sender_avatar else "",  # Đảm bảo convert thành string
                        "content_type": message_type or "text",
                        "has_reply": "true" if conversation_id else "false",
                        "conversation_name": conversation_name or "",
                        "is_group": "true" if is_group else "false",
                        **{str(k): str(v) for k, v in (data or {}).items()}
                    },
                    "android": {
                        "priority": "high",
                        "notification": {
                            "channel_id": "relo_channel",
                            "sound": "default",
                            "click_action": "FLUTTER_NOTIFICATION_CLICK",
                            "image": image_url if image_url else None,
                            "icon": "ic_launcher",
                            "color": "#8B38D7"  # Màu theme của app
                        }
                    },
                    "apns": {
                        "payload": {
                            "aps": {
                                "sound": "default",
                                "badge": 1,
                                "category": "REPLY_CATEGORY" if conversation_id else "DEFAULT_CATEGORY"
                            }
                        },
                        "fcm_options": {
                            "image": image_url if image_url else None
                        }
                    }
                }
            }
            
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(fcm_url, headers=headers, json=message_payload)
                    
                    if response.status_code == 200:
                        successful_tokens.append(token)
                    else:
                        failed_tokens.append(token)
            except Exception as e:
                failed_tokens.append(token)
        
        return successful_tokens
    
    @staticmethod
    async def send_message_notification(
        conversation_id: str,
        sender_id: str,
        sender_name: str,
        message_content: str,
        message_type: str,
        offline_user_ids: List[str],
        sender_avatar: Optional[str] = None,
        image_url: Optional[str] = None,
        conversation_name: Optional[str] = None,
        is_group: bool = False
    ) -> int:
        """
        Gửi push notification cho tin nhắn mới tới các users offline.
        
        Returns:
            Số lượng notifications đã gửi thành công
        """
        
        if not offline_user_ids:
            return 0
        
        # Lấy device tokens của các users offline
        from bson import ObjectId
        user_object_ids = [ObjectId(uid) for uid in offline_user_ids if uid]
        
        if not user_object_ids:
            return 0
        
        users = await User.find(
            {"_id": {"$in": user_object_ids}}
        ).to_list()
        
        all_device_tokens = []
        for user in users:
            if user.deviceTokens:
                all_device_tokens.extend(user.deviceTokens)
        
        if not all_device_tokens:
            return 0
        
        # Format title và body theo style Zalo
        # Title: Tên người gửi hoặc tên nhóm
        if is_group and conversation_name:
            title = conversation_name
            body = f"{sender_name}: {message_content}"
        else:
            title = sender_name
            body = message_content
        
        # Rút gọn body nếu quá dài
        if len(body) > 100:
            body = body[:100] + "..."
        
        # Gửi notification với avatar và image preview
        successful_tokens = await FCMService.send_notification(
            device_tokens=all_device_tokens,
            title=title,
            body=body,
            conversation_id=conversation_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_type=message_type,
            sender_avatar=sender_avatar,
            image_url=image_url,
            conversation_name=conversation_name,
            is_group=is_group
        )
        
        return len(successful_tokens)
    
    @staticmethod
    async def send_group_notification(
        conversation_id: str,
        notification_type: str,
        title: str,
        body: str,
        offline_user_ids: List[str],
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Gửi push notification cho group events (thêm/xóa thành viên).
        
        Returns:
            Số lượng notifications đã gửi thành công
        """
        if not offline_user_ids:
            return 0
        
        # Lấy device tokens của các users offline
        from bson import ObjectId
        user_object_ids = [ObjectId(uid) for uid in offline_user_ids if uid]
        
        if not user_object_ids:
            return 0
        
        users = await User.find(
            {"_id": {"$in": user_object_ids}}
        ).to_list()
        
        all_device_tokens = []
        for user in users:
            if user.deviceTokens:
                all_device_tokens.extend(user.deviceTokens)
        
        if not all_device_tokens:
            return 0
        
        # Gửi notification
        successful_tokens = await FCMService.send_notification(
            device_tokens=all_device_tokens,
            title=title,
            body=body,
            conversation_id=conversation_id,
            data={
                "notification_type": notification_type,
                **(metadata or {})
            }
        )
        
        return len(successful_tokens)

