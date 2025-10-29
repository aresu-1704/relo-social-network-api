from fastapi import APIRouter, Depends, HTTPException
from ..services.notification_service import NotificationService
from ..security import get_current_user_id
from typing import Optional

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/")
async def get_notifications(
    limit: int = 50,
    skip: int = 0,
    unread_only: bool = False,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Lấy danh sách thông báo của người dùng hiện tại
    """
    try:
        notifications = await NotificationService.get_user_notifications(
            user_id=current_user_id,
            limit=limit,
            skip=skip,
            unread_only=unread_only
        )
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unread-count")
async def get_unread_count(
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Lấy số lượng thông báo chưa đọc
    """
    try:
        count = await NotificationService.get_unread_count(current_user_id)
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Đánh dấu một thông báo là đã đọc
    """
    try:
        notification = await NotificationService.mark_as_read(
            notification_id=notification_id,
            user_id=current_user_id
        )
        return {"message": "Đã đánh dấu đã đọc", "notification": notification}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/read-all")
async def mark_all_notifications_as_read(
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Đánh dấu tất cả thông báo là đã đọc
    """
    try:
        await NotificationService.mark_all_as_read(current_user_id)
        return {"message": "Đã đánh dấu tất cả là đã đọc"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Xóa một thông báo
    """
    try:
        await NotificationService.delete_notification(
            notification_id=notification_id,
            user_id=current_user_id
        )
        return {"message": "Đã xóa thông báo"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

