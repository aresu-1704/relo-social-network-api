import os
import json
import base64
import httpx
from typing import List, Optional, Dict, Any
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
        conversation_avatar: Optional[str] = None,
        conversation_name: Optional[str] = None,
        is_group: bool = False,
        token_to_user_map: Optional[Dict[str, Any]] = None,
        screen: Optional[str] = None  # Thêm tham số để chỉ định màn hình cần mở
    ) -> tuple[List[str], List[str]]:
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
            return []
        
        # Lấy project_id từ credentials
        project_id = None
        if FCMService._credentials:
            project_id = FCMService._credentials.project_id
        
        if not project_id:
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
        for i, token in enumerate(device_tokens):
            # FCM v1 API format - DATA ONLY để client tự hiển thị local notification
            # Không có notification field = Firebase sẽ KHÔNG tự hiển thị
            # Client sẽ nhận qua onMessage và tự hiển thị local notification với avatar, button reply
            message_payload = {
                "message": {
                    "token": token,
                    # KHÔNG có notification field - để client tự hiển thị local notification
                    "data": {
                        "type": message_type or "message",
                        "conversation_id": conversation_id or "",
                        "sender_id": sender_id or "",
                        "sender_name": sender_name or "",
                        "sender_avatar": str(sender_avatar) if sender_avatar else "",
                        "content_type": message_type or "text",
                        "has_reply": "true" if conversation_id else "false",
                        "conversation_name": conversation_name or "",
                        "conversation_avatar": str(conversation_avatar) if conversation_avatar else "",
                        # Flag quan trọng: phân biệt chat nhóm và chat 1-1
                        # "true" = chat nhóm, "false" = chat 1-1
                        "is_group": "true" if is_group else "false",
                        "title": title,
                        "body": body,
                        # Thông tin thành viên cho chat nhóm (sẽ được ghi đè từ data nếu có)
                        "member_ids": "",
                        "member_count": "0",
                        # Thêm screen để chỉ định màn hình cần mở
                        "screen": screen or ("chat" if conversation_id else ""),
                        **{str(k): str(v) for k, v in (data or {}).items()}
                    },
                    "android": {
                        "priority": "high",
                        # Không có notification field trong android = data-only message
                    },
                    "apns": {
                        "headers": {
                            "apns-priority": "10"
                        },
                        "payload": {
                            "aps": {
                                "content-available": 1,  # Background data-only
                                "sound": "default",
                                "badge": 1
                            }
                        },
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
                        
                        # Xóa token không hợp lệ (404, 400 với invalid token) khỏi database
                        if response.status_code in [404, 400]:
                            response_data = response.json() if response.text else {}
                            error_code = response_data.get("error", {}).get("code", 0)
                            error_message = response_data.get("error", {}).get("message", "")
                            
                            # 404 hoặc 400 thường có nghĩa token không hợp lệ
                            if response.status_code == 404 or (response.status_code == 400 and "token" in error_message.lower()):
                                if token_to_user_map and token in token_to_user_map:
                                    user = token_to_user_map[token]
                                    if token in user.deviceTokens:
                                        user.deviceTokens.remove(token)
                                        await user.save()
            except Exception as e:
                failed_tokens.append(token)
        
        return successful_tokens, failed_tokens
    
    @staticmethod
    async def send_message_notification(
        conversation_id: str,
        sender_id: str,
        sender_name: str,
        message_content: str,
        message_type: str,
        offline_user_ids: List[str],
        sender_avatar: Optional[str] = None,
        conversation_name: Optional[str] = None,
        is_group: bool = False,
        group_avatar_url: Optional[str] = None,
        member_ids: Optional[List[str]] = None,
    ) -> int:
        """
        Gửi push notification cho tin nhắn mới tới các users offline.
        """
        if not offline_user_ids:
            return 0

        from bson import ObjectId
        user_object_ids = [ObjectId(uid) for uid in offline_user_ids if uid]
        if not user_object_ids:
            return 0

        users = await User.find({"_id": {"$in": user_object_ids}}).to_list()

        token_to_user_map = {}
        all_device_tokens = []
        for user in users:
            if user.deviceTokens:
                for token in user.deviceTokens:
                    token_to_user_map[token] = user
                all_device_tokens.extend(user.deviceTokens)

        if not all_device_tokens:
            return 0

        # --- Format thông tin hiển thị ---
        # PHÂN BIỆT CHAT NHÓM VÀ CHAT 1-1:
        # - Chat nhóm (is_group=True): 
        #   + Title = tên nhóm (hoặc "Cuộc trò chuyện")
        #   + Body = "Tên người gửi: Nội dung"
        #   + Avatar = conversation_avatar (ảnh nhóm)
        # - Chat 1-1 (is_group=False):
        #   + Title = tên người gửi
        #   + Body = nội dung tin nhắn
        #   + Avatar = sender_avatar (ảnh người gửi), KHÔNG dùng conversation_avatar
        if is_group:
            # CHAT NHÓM: hiển thị tên nhóm và avatar nhóm
            # Đảm bảo có tên nhóm (fallback "Cuộc trò chuyện")
            final_conversation_name = (
                conversation_name.strip()
                if conversation_name and conversation_name.strip()
                else "Cuộc trò chuyện"
            )
            title = final_conversation_name
            body = f"{sender_name}: {message_content}"  # Thêm tên người gửi vào body
            avatar_to_use = group_avatar_url  # Ảnh nhóm (có thể None)
        else:
            # CHAT 1-1: hiển thị tên người gửi và avatar người gửi
            title = sender_name if sender_name and sender_name.strip() else "Người dùng"
            body = message_content  # Chỉ nội dung tin nhắn, không có tên người gửi
            avatar_to_use = None  # Chat 1-1 KHÔNG dùng conversation_avatar, chỉ dùng sender_avatar

        # Rút gọn body cho an toàn
        if len(body) > 100:
            body = body[:100] + "..."

        # Đảm bảo conversation_name không None
        final_conversation_name_to_send = (
            final_conversation_name if is_group 
            else (conversation_name or "")
        )

        # Chuẩn bị data payload với member_ids và member_count
        additional_data = None
        if is_group and member_ids:
            additional_data = {
                "member_ids": ",".join(member_ids),
                "member_count": str(len(member_ids))
            }
        
        successful_tokens = await FCMService.send_notification(
            device_tokens=all_device_tokens,
            title=title,
            body=body,
            conversation_id=conversation_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_type=message_type,
            sender_avatar=sender_avatar,
            conversation_name=final_conversation_name_to_send,
            conversation_avatar=avatar_to_use,  # Ảnh nhóm nếu group (có thể None), None nếu 1-1
            is_group=is_group,
            token_to_user_map=token_to_user_map,
            data=additional_data,
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
        
        # Lưu mapping token -> user để xóa token không hợp lệ sau này
        token_to_user_map = {}
        all_device_tokens = []
        for user in users:
            if user.deviceTokens:
                for token in user.deviceTokens:
                    token_to_user_map[token] = user
                all_device_tokens.extend(user.deviceTokens)
        
        if not all_device_tokens:
            return 0
        
        # Gửi notification
        successful_tokens, _ = await FCMService.send_notification(
            device_tokens=all_device_tokens,
            title=title,
            body=body,
            conversation_id=conversation_id,
            data={
                "notification_type": notification_type,
                **(metadata or {})
            },
            token_to_user_map=token_to_user_map
        )
        
        return len(successful_tokens)
    
    @staticmethod
    async def send_friend_request_notification(
        from_user_id: str,
        from_user_name: str,
        from_user_avatar: Optional[str],
        to_user_id: str
    ) -> int:
        """
        Gửi push notification khi có lời mời kết bạn mới.
        
        Args:
            from_user_id: ID của người gửi lời mời
            from_user_name: Tên hiển thị của người gửi
            from_user_avatar: Avatar URL của người gửi
            to_user_id: ID của người nhận lời mời
        
        Returns:
            Số lượng notifications đã gửi thành công
        """
        # Lấy device tokens của người nhận
        from bson import ObjectId
        try:
            to_user_object_id = ObjectId(to_user_id)
        except:
            return 0
        
        to_user = await User.get(to_user_object_id)
        if not to_user or not to_user.deviceTokens:
            return 0
        
        # Tạo token mapping
        token_to_user_map = {}
        for token in to_user.deviceTokens:
            token_to_user_map[token] = to_user
        
        title = "Lời mời kết bạn"
        body = f"{from_user_name} muốn kết bạn với bạn"
        
        successful_tokens, failed_tokens = await FCMService.send_notification(
            device_tokens=to_user.deviceTokens,
            title=title,
            body=body,
            conversation_id=None,
            sender_id=from_user_id,
            sender_name=from_user_name,
            message_type="friend_request",
            sender_avatar=from_user_avatar,
            conversation_name=None,
            is_group=False,
            token_to_user_map=token_to_user_map,
            screen="friend_requests",
            data={
                "type": "friend_request",
                "from_user_id": from_user_id,
                "from_user_name": from_user_name,
            }
        )
        
        return len(successful_tokens)

