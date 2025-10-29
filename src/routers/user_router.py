from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Body, Form
from typing import List
from ..services import UserService
from ..schemas import FriendRequestCreate, FriendRequestResponse, UserPublic, UserUpdate, UserSearchResult
from ..schemas.block_schema import BlockUserRequest
from ..schemas import FriendRequestPublic
from ..models import User
from ..security import get_current_user

router = APIRouter(tags=["User"])

# Lấy thông tin nhiều người dùng theo danh sách ID
@router.post("/batch", response_model=List[UserPublic])
async def get_users_by_ids(
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """Lấy thông tin nhiều người dùng theo danh sách ID."""
    try:
        user_ids = request.get('user_ids', [])
        if not user_ids:
            user_ids = request  # Fallback: assume request is the array itself
        
        users = await UserService.get_users_by_ids(user_ids)
        # Convert User objects to dict để tránh Pydantic validation error
        user_dicts = []
        for user in users:
            user_dict = {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "displayName": user.displayName,
                "avatarUrl": user.avatarUrl,
                "backgroundUrl": user.backgroundUrl,
                "bio": user.bio,
                "createdAt": user.createdAt.isoformat() if user.createdAt else None
            }
            user_dicts.append(user_dict)
        return user_dicts
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Lấy hồ sơ của người dùng hiện tại
@router.get("/me", response_model=UserPublic)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Lấy hồ sơ của người dùng hiện được xác thực.
    """
    return UserPublic(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        displayName=current_user.displayName,
        avatarUrl=current_user.avatarUrl,
        backgroundUrl=current_user.backgroundUrl,
        bio=current_user.bio
    )

# Cập nhật hồ sơ của người dùng hiện tại
@router.put("/me")
async def update_user_me(
    displayName: str = Form(None),
    bio: str = Form(None),
    avatar: UploadFile = File(None),
    background: UploadFile = File(None),
    current_user: User = Depends(get_current_user)
):
    """
    Cập nhật hồ sơ của người dùng hiện tại.
    Nhận form-data với các file upload cho avatar và background.
    """
    try:
        # Tạo UserUpdate từ form data
        user_update_data = {}
        if displayName is not None:
            user_update_data["displayName"] = displayName
        if bio is not None:
            user_update_data["bio"] = bio
        
        # Tạo UserUpdate object
        user_update = UserUpdate(**user_update_data)
        
        # Upload files nếu có và cập nhật text fields cùng lúc
        updated_user = current_user
        
        if avatar:
            updated_user = await UserService.update_user_avatar(
                user_id=str(current_user.id),
                avatar_file=avatar
            )
        
        if background:
            updated_user = await UserService.update_user_background(
                user_id=str(current_user.id),
                background_file=background
            )
        
        # Cập nhật text fields nếu có
        if displayName is not None or bio is not None:
            updated_user = await UserService.update_user(
                user_id=str(updated_user.id),
                user_update=user_update
            )
        
        return {
            "message": "Cập nhật thành công.",
            "user": {
                "id": str(updated_user.id),
                "displayName": updated_user.displayName,
                "bio": updated_user.bio,
                "avatarUrl": updated_user.avatarUrl,
                "backgroundUrl": updated_user.backgroundUrl,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Gửi yêu cầu kết bạn
@router.post("/friend-request", status_code=201)
async def send_friend_request(
    request_data: FriendRequestCreate,
    current_user: User = Depends(get_current_user)
):
    try:
        to_user_id = request_data.to_user_id
        
        result = await UserService.send_friend_request(from_user_id=str(current_user.id), to_user_id=to_user_id)
        
        return {"message": "Gửi yêu cầu kết bạn thành công."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Hủy lời mời kết bạn
@router.delete("/friend-request/{user_id}", status_code=200)
async def cancel_friend_request(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        result = await UserService.cancel_friend_request(str(current_user.id), user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Phản hồi yêu cầu kết bạn
@router.post("/friend-request/{request_id}", status_code=200)
async def respond_to_friend_request(
    request_id: str,
    response_data: FriendRequestResponse,
    current_user: User = Depends(get_current_user)
):
    try:
        await UserService.respond_to_friend_request(
            request_id=request_id,
            user_id=str(current_user.id),
            response=response_data.response
        )
        return {"message": f"Yêu cầu kết bạn đã được {response_data.response}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Phản hồi yêu cầu kết bạn theo from_user_id
@router.post("/friend-request/by-user/{from_user_id}", status_code=200)
async def respond_to_friend_request_by_user(
    from_user_id: str,
    response_data: FriendRequestResponse,
    current_user: User = Depends(get_current_user)
):
    try:
        await UserService.respond_to_friend_request_by_from_user(
            from_user_id=from_user_id,
            current_user_id=str(current_user.id),
            response=response_data.response
        )
        return {"message": f"Yêu cầu kết bạn đã được {response_data.response}."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Lấy danh sách lời mời kết bạn đang chờ
@router.get("/friend-requests/pending")
async def get_pending_friend_requests(current_user: User = Depends(get_current_user)):
    """
    Lấy danh sách các lời mời kết bạn đang chờ xử lý cho người dùng hiện tại.
    """
    try:
        pending_requests = await UserService.get_friend_requests(user_id=str(current_user.id))
        return pending_requests

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Lấy danh sách bạn bè
@router.get("/friends")
async def get_friends(current_user: User = Depends(get_current_user)):
    """
    Lấy danh sách bạn bè cho người dùng hiện được xác thực.
    """
    try:
        friends = await UserService.get_friends(user_id=str(current_user.id))
        return [
            {
                "id": str(friend.id),
                "username": friend.username,
                "email": friend.email,
                "displayName": friend.displayName,
                "avatarUrl": friend.avatarUrl,
            } for friend in friends
        ]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Tìm kiếm người dùng
@router.get("/search")
async def search_users(query: str = Query(..., min_length=1), current_user: User = Depends(get_current_user)):
    """
    Tìm kiếm người dùng theo username hoặc displayName.
    """
    try:
        user_results = await UserService.search_users(query, str(current_user.id))
        
        # Format response with friend status
        result = []
        for item in user_results:
            user = item['user']
            friend_status = item['friendStatus']
            
            result.append({
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "avatarUrl": user.avatarUrl,
                "displayName": user.displayName,
                "backgroundUrl": user.backgroundUrl,
                "bio": user.bio,
                "friendStatus": friend_status  # 'friends', 'pending_sent', 'pending_received', 'none'
            })
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Lấy hồ sơ công khai của người dùng
@router.get("/{user_id}")
async def get_user_profile(user_id: str, current_user: User = Depends(get_current_user)):
    """
    Lấy hồ sơ công khai của bất kỳ người dùng nào.
    """
    try:
        return await UserService.get_user_profile(user_id, str(current_user.id))
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Chặn người dùng
@router.post("/block", status_code=200)
async def block_user(request: BlockUserRequest, current_user: User = Depends(get_current_user)):
    try:
        result = await UserService.block_user(str(current_user.id), request.user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Bỏ chặn người dùng
@router.post("/unblock", status_code=200)
async def unblock_user(request: BlockUserRequest, current_user: User = Depends(get_current_user)):
    try:
        result = await UserService.unblock_user(str(current_user.id), request.user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Lấy danh sách người dùng bị chặn
@router.get("/blocked-lists/{user_id}")
async def get_blocked_users(user_id: str, current_user: User = Depends(get_current_user)):
    """
    Lấy danh sách người dùng bị chặn của người dùng hiện tại.
    """
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Không có quyền truy cập danh sách người dùng bị chặn của người khác.")
    
    try:
        blocked_users = await UserService.get_blocked_users(user_id)
        return blocked_users
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Kiểm tra trạng thái block giữa 2 người dùng
@router.get("/block-status/{other_user_id}")
async def check_block_status(
    other_user_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Kiểm tra trạng thái block giữa current_user và other_user_id.
    """
    try:
        result = await UserService.check_block_status(
            str(current_user.id),
            other_user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Kiểm tra trạng thái kết bạn
@router.get("/{user_id}/friend-status")
async def check_friend_status(user_id: str, current_user: User = Depends(get_current_user)):
    """
    Kiểm tra trạng thái kết bạn giữa người dùng hiện tại và người dùng khác.
    """
    try:
        status = await UserService.check_friend_status(str(current_user.id), user_id)
        return {"status": status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Hủy kết bạn
@router.post("/{user_id}/unfriend", status_code=200)
async def unfriend_user(user_id: str, current_user: User = Depends(get_current_user)):
    """
    Hủy kết bạn với một người dùng.
    """
    try:
        result = await UserService.unfriend_user(str(current_user.id), user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Xóa tài khoản (soft delete)
@router.delete("/me", status_code=200)
async def delete_account(current_user: User = Depends(get_current_user)):
    """
    Xóa tài khoản người dùng (soft delete).
    Đổi status thành 'deleted' thay vì xóa khỏi database.
    """
    try:
        result = await UserService.delete_account(str(current_user.id))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))