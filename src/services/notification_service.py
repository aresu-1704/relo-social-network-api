from datetime import datetime
from typing import List, Optional
from ..models import Notification
from ..models import User
from bson import ObjectId


class NotificationService:
    """
    Service xử lý các thông báo của người dùng
    """
    
    @staticmethod
    async def create_notification(
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        metadata: dict = None
    ):
        """
        Tạo một thông báo mới cho người dùng
        
        Args:
            user_id: ID của người dùng nhận thông báo
            notification_type: Loại thông báo (friend_request_accepted, friend_request_rejected, new_post, etc.)
            title: Tiêu đề thông báo
            message: Nội dung thông báo
            metadata: Thông tin bổ sung (userId của người gửi, postId, etc.)
        """
        notification = Notification(
            userId=user_id,
            type=notification_type,
            title=title,
            message=message,
            metadata=metadata or {},
            isRead=False,
            createdAt=datetime.now()
        )
        await notification.save()
        return notification
    
    @staticmethod
    async def get_user_notifications(
        user_id: str,
        limit: int = 50,
        skip: int = 0,
        unread_only: bool = False
    ) -> List[dict]:
        """
        Lấy danh sách thông báo của người dùng
        
        Args:
            user_id: ID của người dùng
            limit: Số lượng thông báo tối đa
            skip: Số thông báo bỏ qua (phân trang)
            unread_only: Chỉ lấy thông báo chưa đọc
        """
        query = {"userId": user_id}
        
        if unread_only:
            query["isRead"] = False
        
        # Lấy thông báo, sắp xếp theo thời gian giảm dần
        notifications = await Notification.find(
            query,
            limit=limit,
            skip=skip
        ).sort(-Notification.createdAt).to_list()
        
        # Chuyển đổi sang dictionary
        result = []
        for notif in notifications:
            result.append({
                "id": str(notif.id),
                "userId": notif.userId,
                "type": notif.type,
                "title": notif.title,
                "message": notif.message,
                "metadata": notif.metadata,
                "isRead": notif.isRead,
                "createdAt": notif.createdAt.isoformat()
            })
        
        return result
    
    @staticmethod
    async def mark_as_read(notification_id: str, user_id: str):
        """
        Đánh dấu một thông báo là đã đọc
        
        Args:
            notification_id: ID của thông báo
            user_id: ID của người dùng (để đảm bảo người dùng chỉ đánh dấu thông báo của họ)
        """
        notification = await Notification.get(notification_id)
        
        if not notification:
            raise ValueError("Không tìm thấy thông báo")
        
        if notification.userId != user_id:
            raise ValueError("Không có quyền đánh dấu thông báo này")
        
        notification.isRead = True
        await notification.save()
        return notification
    
    @staticmethod
    async def mark_all_as_read(user_id: str):
        """
        Đánh dấu tất cả thông báo của người dùng là đã đọc
        """
        await Notification.find({"userId": user_id, "isRead": False}).update(
            {"$set": {"isRead": True}}
        )
    
    @staticmethod
    async def delete_notification(notification_id: str, user_id: str):
        """
        Xóa một thông báo
        
        Args:
            notification_id: ID của thông báo
            user_id: ID của người dùng (để đảm bảo người dùng chỉ xóa thông báo của họ)
        """
        notification = await Notification.get(notification_id)
        
        if not notification:
            raise ValueError("Không tìm thấy thông báo")
        
        if notification.userId != user_id:
            raise ValueError("Không có quyền xóa thông báo này")
        
        await notification.delete()
    
    @staticmethod
    async def get_unread_count(user_id: str) -> int:
        """
        Lấy số lượng thông báo chưa đọc của người dùng
        """
        count = await Notification.find({"userId": user_id, "isRead": False}).count()
        return count

