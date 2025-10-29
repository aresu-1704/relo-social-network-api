# api/src/websocket.py
from typing import Dict, List, Any
from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from datetime import datetime
from .models import User
from .security import get_current_user_ws

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Ánh xạ user_id tới danh sách các kết nối WebSocket đang hoạt động
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """Đăng ký một kết nối WebSocket mới cho một người dùng."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        """Xóa một kết nối WebSocket."""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    def _serialize_for_json(self, obj: Any) -> Any:
        """Chuyển đổi datetime thành ISO string để gửi qua JSON."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._serialize_for_json(v) for v in obj]
        return obj

    async def broadcast_to_user(self, user_id: str, data: dict):
        """Gửi một tin nhắn JSON đến tất cả các kết nối đang hoạt động của một người dùng."""
        
        if user_id in self.active_connections:
            json_ready_data = self._serialize_for_json(data)
            for connection in self.active_connections[user_id]:
                await connection.send_json(json_ready_data)

    
    def is_user_online(self, user_id: str) -> bool:
        """Kiểm tra user có đang online (có WebSocket connection) không."""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0
    
    def get_offline_users(self, user_ids: List[str]) -> List[str]:
        """Lấy danh sách users đang offline từ danh sách user IDs."""
        return [uid for uid in user_ids if not self.is_user_online(uid)]

# Tạo một instance duy nhất dùng toàn app
manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, user: User = Depends(get_current_user_ws)):
    user_id = str(user.id)
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Chờ tin nhắn từ client
            data = await websocket.receive_text()
            # Handle incoming messages if needed in the future
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, websocket)
