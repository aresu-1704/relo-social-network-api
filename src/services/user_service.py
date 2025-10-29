import asyncio
import os
from datetime import datetime
from typing import List
from fastapi import UploadFile
from ..models import User
from ..models import FriendRequest
from ..schemas import UserUpdate
from ..websocket import manager
from ..services.notification_service import NotificationService
from bson import ObjectId
import base64
import tempfile
from cloudinary.uploader import upload as cloudinary_upload, destroy

class UserService:

    @staticmethod
    async def send_friend_request(from_user_id: str, to_user_id: str):
        """
        Gửi một yêu cầu kết bạn từ người dùng này đến người dùng khác.
        """
        if from_user_id == to_user_id:
            raise ValueError("Không thể gửi yêu cầu kết bạn cho chính mình.")

        # Lấy thông tin người gửi để kiểm tra danh sách bạn bè
        from_user = await User.get(from_user_id)
        if not from_user:
            raise ValueError("Không tìm thấy người dùng gửi.")

        # Kiểm tra xem họ đã là bạn bè chưa
        if to_user_id in from_user.friendIds:
            raise ValueError("Người dùng đã là bạn bè.")

        # Kiểm tra xem một yêu cầu đang chờ xử lý hoặc đã được chấp nhận có tồn tại không
        existing_request = await FriendRequest.find_one(
            {
                "$or": [
                    {"fromUserId": from_user_id, "toUserId": to_user_id},
                    {"fromUserId": to_user_id, "toUserId": from_user_id}
                ],
                "status": {"$in": ["pending", "accepted"]}
            }
        )
        if existing_request:
            raise ValueError("Một yêu cầu kết bạn đã tồn tại hoặc đang chờ xử lý.")

        # Tạo và lưu yêu cầu mới
        new_request = FriendRequest(fromUserId=from_user_id, toUserId=to_user_id)
        await new_request.save()

        # Gửi thông báo real-time đến người nhận yêu cầu
        notification_payload = {
            "type": "friend_request_received",
            "payload": {
                "request_id": str(new_request.id),
                "from_user_id": str(from_user.id),
                "displayName": from_user.displayName,
                "avatar": from_user.avatarUrl
            }
        }
        asyncio.create_task(
            manager.broadcast_to_user(to_user_id, notification_payload)
        )

        return new_request

    @staticmethod
    async def cancel_friend_request(from_user_id: str, to_user_id: str):
        """
        Hủy một lời mời kết bạn đã gửi.
        """
        # Tìm friend request pending từ from_user_id tới to_user_id
        request = await FriendRequest.find_one({
            "fromUserId": from_user_id,
            "toUserId": to_user_id,
            "status": "pending"
        })
        
        if not request:
            raise ValueError("Không tìm thấy lời mời kết bạn để hủy.")
        
        # Xóa friend request
        await request.delete()
        
        return {"message": "Đã hủy lời mời kết bạn thành công."}

    @staticmethod
    async def respond_to_friend_request(request_id: str, user_id: str, response: str):
        """
        Phản hồi một yêu cầu kết bạn ('accept' hoặc 'reject').
        """
        # Lấy yêu cầu kết bạn bằng ID
        friend_request = await FriendRequest.get(request_id)
        if not friend_request or friend_request.toUserId != user_id:
            raise ValueError("Không tìm thấy yêu cầu kết bạn hoặc bạn không phải là người nhận.")

        if friend_request.status != 'pending':
            raise ValueError("Yêu cầu kết bạn này đã được phản hồi.")

        if response == 'accept':
            # Lấy cả hai người dùng để cập nhật danh sách bạn bè của họ
            from_user = await User.get(friend_request.fromUserId)
            to_user = await User.get(friend_request.toUserId)

            if not from_user or not to_user:
                raise ValueError("Không tìm thấy một trong hai người dùng.")

            # Thêm ID bạn bè vào danh sách của nhau (dùng string ID)
            to_user_id_str = str(to_user.id)
            from_user_id_str = str(from_user.id)
            
            if to_user_id_str not in from_user.friendIds:
                from_user.friendIds.append(to_user_id_str)
            if from_user_id_str not in to_user.friendIds:
                to_user.friendIds.append(from_user_id_str)

            # Lưu các thay đổi vào cơ sở dữ liệu
            await from_user.save()
            await to_user.save()
            
            # Xóa friend request khỏi database sau khi đã chấp nhận
            await friend_request.delete()
            
            # Tạo notification cho người gửi yêu cầu (người được chấp nhận)
            await NotificationService.create_notification(
                user_id=friend_request.fromUserId,
                notification_type="friend_request_accepted",
                title="Đã chấp nhận lời mời kết bạn",
                message=f"{to_user.displayName} đã chấp nhận lời mời kết bạn của bạn",
                metadata={"userId": str(to_user.id), "displayName": to_user.displayName, "avatarUrl": to_user.avatarUrl}
            )
            
            # Gửi thông báo real-time đến cả hai người
            # Gửi cho người gửi yêu cầu
            notification_payload_from = {
                "type": "friend_request_accepted",
                "payload": {
                    "user_id": str(to_user.id),
                    "displayName": to_user.displayName,
                    "avatarUrl": to_user.avatarUrl
                }
            }
            asyncio.create_task(
                manager.broadcast_to_user(friend_request.fromUserId, notification_payload_from)
            )
            
            # Gửi cho người chấp nhận
            notification_payload_to = {
                "type": "friend_added",
                "payload": {
                    "user_id": str(from_user.id),
                    "displayName": from_user.displayName,
                    "avatarUrl": from_user.avatarUrl
                }
            }
            asyncio.create_task(
                manager.broadcast_to_user(str(to_user.id), notification_payload_to)
            )

        elif response == 'reject':
            # Từ chối yêu cầu - xóa khỏi database
            await friend_request.delete()
            
            # Tạo notification cho người gửi yêu cầu (người bị từ chối)
            to_user = await User.get(friend_request.toUserId)
            await NotificationService.create_notification(
                user_id=friend_request.fromUserId,
                notification_type="friend_request_rejected",
                title="Đã từ chối lời mời kết bạn",
                message=f"{to_user.displayName} đã từ chối lời mời kết bạn của bạn",
                metadata={"userId": str(to_user.id), "displayName": to_user.displayName, "avatarUrl": to_user.avatarUrl}
            )
            
            # Broadcast notification đến người gửi yêu cầu
            from_user = await User.get(friend_request.fromUserId)
            if from_user:
                notification_payload = {
                    "type": "friend_request_declined",
                    "payload": {
                        "user_id": str(friend_request.toUserId)
                    }
                }
                asyncio.create_task(
                    manager.broadcast_to_user(friend_request.fromUserId, notification_payload)
                )
        else:
            raise ValueError("Phản hồi không hợp lệ. Phải là 'accept' hoặc 'reject'.")
        
        return friend_request
    
    @staticmethod
    async def get_users_by_ids(user_ids: List[str]) -> List[User]:
        """Lấy danh sách người dùng theo danh sách ID."""
        try:
            # Convert string IDs to ObjectId với validation
            object_ids = []
            for user_id in user_ids:
                if ObjectId.is_valid(user_id):
                    object_ids.append(ObjectId(user_id))
            
            users = await User.find({"_id": {"$in": object_ids}}).to_list()
            return users
        except Exception as e:
            raise Exception(f"Failed to get users by IDs: {e}")

    @staticmethod
    async def respond_to_friend_request_by_from_user(from_user_id: str, current_user_id: str, response: str):
        """
        Phản hồi một yêu cầu kết bạn dựa vào from_user_id ('accept' hoặc 'reject').
        """
        # Tìm friend request từ from_user_id tới current_user_id
        friend_request = await FriendRequest.find_one({
            "fromUserId": from_user_id,
            "toUserId": current_user_id,
            "status": "pending"
        })
        
        if not friend_request:
            raise ValueError("Không tìm thấy yêu cầu kết bạn.")
        
        # Sử dụng lại logic từ respond_to_friend_request
        request_id = str(friend_request.id)
        return await UserService.respond_to_friend_request(request_id, current_user_id, response)

    @staticmethod
    async def get_friend_requests(user_id: str):
        """
        Lấy danh sách các lời mời kết bạn đang chờ xử lý cho một người dùng.
        Trả về danh sách kèm thông tin người gửi.
        """
        # Tìm tất cả các yêu cầu kết bạn đang chờ xử lý gửi đến người dùng
        pending_requests = await FriendRequest.find(
            {
                "toUserId": user_id,
                "status": "pending"
            }
        ).to_list()
        
        # Lấy thông tin người gửi
        result = []
        for req in pending_requests:
            try:
                from_user = await User.get(req.fromUserId)
                if from_user:
                    result.append({
                        "id": str(req.id),
                        "fromUserId": req.fromUserId,
                        "toUserId": req.toUserId,
                        "status": req.status,
                        "createdAt": req.createdAt,
                        "fromUser": {
                            "id": str(from_user.id),
                            "username": from_user.username,
                            "displayName": from_user.displayName,
                            "avatarUrl": from_user.avatarUrl if from_user.avatarUrl else None,
                        }
                    })
            except:
                # Skip if user not found
                continue
        
        return result

    @staticmethod
    async def get_friends(user_id: str):
        """
        Lấy danh sách bạn bè đầy đủ của người dùng với chi tiết người dùng.
        """
        # Lấy thông tin người dùng
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Lấy tất cả bạn bè trong một truy vấn
        friends = await User.find({"_id": {"$in": [ObjectId(fid) for fid in user.friendIds]}}).to_list()
        
        return friends

    @staticmethod
    async def get_user_profile(user_id: str, current_user_id: str):
        """
        Lấy hồ sơ công khai của bất kỳ người dùng nào, trừ khi bị chặn.
        """
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng")

        current_user = await User.get(current_user_id)
        if not current_user:
            raise ValueError("Không tìm thấy người dùng hiện tại")

        # Kiểm tra xem người dùng hiện tại có bị người dùng kia chặn không
        if current_user_id in user.blockedUserIds:
            raise ValueError("Bạn đã bị người dùng này chặn.")

        # Kiểm tra xem người dùng hiện tại có chặn người dùng kia không
        if user_id in current_user.blockedUserIds:
            raise ValueError("Bạn đã chặn người dùng này.")

        # Trả về trực tiếp dictionary thay vì tạo đối tượng User mới
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "displayName": user.displayName,
            "avatarUrl": user.avatarUrl if user.avatarUrl not in ["", None] else None,
            "backgroundUrl": user.backgroundUrl if user.backgroundUrl not in ["", None] else None,
            "bio": user.bio if user.bio not in ["", None] else None,
            "createdAt": user.createdAt.isoformat() if user.createdAt else None
        }

    @staticmethod
    async def block_user(user_id: str, block_user_id: str):
        """
        Chặn một người dùng và tự động hủy kết bạn.
        """
        if user_id == block_user_id:
            raise ValueError("Không thể tự chặn chính mình.")

        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")

        blocked_user = await User.get(block_user_id)
        if not blocked_user:
            raise ValueError("Không tìm thấy người dùng bị chặn.")

        # Chặn người dùng
        if block_user_id not in user.blockedUserIds:
            user.blockedUserIds.append(block_user_id)
        
        # Hủy kết bạn từ phía user (người chặn)
        if block_user_id in user.friendIds:
            user.friendIds.remove(block_user_id)
        
        await user.save()

        # Hủy kết bạn từ phía blocked_user (người bị chặn)
        if user_id in blocked_user.friendIds:
            blocked_user.friendIds.remove(user_id)
            await blocked_user.save()

        # Broadcast notification đến cả hai user
        # Gửi cho người chặn
        notification_payload_blocker = {
            "type": "user_blocked",
            "payload": {
                "user_id": str(blocked_user.id),
                "displayName": blocked_user.displayName
            }
        }
        asyncio.create_task(
            manager.broadcast_to_user(user_id, notification_payload_blocker)
        )
        
        # Gửi cho người bị chặn
        notification_payload_blocked = {
            "type": "you_were_blocked",
            "payload": {
                "user_id": str(user.id),
                "displayName": user.displayName
            }
        }
        asyncio.create_task(
            manager.broadcast_to_user(block_user_id, notification_payload_blocked)
        )

        return {"message": "Người dùng đã bị chặn thành công."}

    @staticmethod
    async def unblock_user(user_id: str, block_user_id: str):
        """
        Bỏ chặn một người dùng.
        """
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")

        if block_user_id in user.blockedUserIds:
            user.blockedUserIds.remove(block_user_id)
            await user.save()
            
            # Broadcast notification đến người bỏ chặn
            blocked_user = await User.get(block_user_id)
            if blocked_user:
                notification_payload = {
                    "type": "user_unblocked",
                    "payload": {
                        "user_id": str(blocked_user.id),
                        "displayName": blocked_user.displayName
                    }
                }
                asyncio.create_task(
                    manager.broadcast_to_user(user_id, notification_payload)
                )

        return {"message": "Người dùng đã được bỏ chặn thành công."}

    @staticmethod
    async def search_users(query: str, current_user_id: str):
        """
        Tìm kiếm người dùng theo username hoặc displayName, loại trừ những người dùng bị chặn.
        """
        current_user = await User.get(current_user_id)
        if not current_user:
            raise ValueError("Không tìm thấy người dùng hiện tại.")

        # Lấy danh sách những người dùng đã chặn người dùng hiện tại
        users_blocking_me = await User.find({"blockedUserIds": current_user_id}).to_list()
        ids_blocking_me = [str(u.id) for u in users_blocking_me]

        # Tổng hợp danh sách ID bị chặn (bao gồm cả current_user và deleted users)
        excluded_ids = current_user.blockedUserIds + ids_blocking_me + [current_user_id]

        # Tìm kiếm người dùng (loại trừ deleted và blocked)
        users = await User.find(
            {
                "$or": [
                    {"username": {"$regex": query, "$options": "i"}},
                    {"displayName": {"$regex": query, "$options": "i"}}
                ],
                "_id": {"$nin": [ObjectId(uid) for uid in excluded_ids if uid and uid != '']},
                "status": {"$ne": "deleted"}
            }
        ).to_list()

        # Add friend status info for each user
        results = []
        current_user_id_str = str(current_user.id)
        
        for user in users:
            user_id_str = str(user.id)
            
            # Check if friend
            is_friend = user_id_str in current_user.friendIds
            
            if is_friend:
                friend_status = 'friends'
            else:
                # Check pending requests
                sent_request = await FriendRequest.find_one({
                    "fromUserId": current_user_id_str,
                    "toUserId": user_id_str,
                    "status": "pending"
                })
                if sent_request:
                    friend_status = 'pending_sent'
                else:
                    received_request = await FriendRequest.find_one({
                        "fromUserId": user_id_str,
                        "toUserId": current_user_id_str,
                        "status": "pending"
                    })
                    if received_request:
                        friend_status = 'pending_received'
                    else:
                        friend_status = 'none'
            
            # Store with status
            user_data = {
                'user': user,
                'friendStatus': friend_status
            }
            results.append(user_data)

        return results

    @staticmethod
    async def get_users_by_ids(user_ids: list[str]):
        """
        Lấy danh sách người dùng bằng ID của họ.
        Bao gồm cả những tài khoản đã bị xóa.
        """
        if not user_ids:
            return []
        
        # Chuyển đổi chuỗi ID thành ObjectId
        object_ids = [ObjectId(uid) for uid in user_ids]
        
        # Tìm tất cả người dùng có ID trong danh sách (bao gồm cả deleted)
        users = await User.find({"_id": {"$in": object_ids}}).to_list()
        return users

    @staticmethod
    async def check_friend_status(user_id: str, target_user_id: str):
        """
        Kiểm tra trạng thái kết bạn giữa hai người dùng.
        Trả về: 'friends', 'pending_sent', 'pending_received', 'none'
        """
        if user_id == target_user_id:
            return 'self'
        
        # Lấy thông tin người dùng hiện tại
        current_user = await User.get(user_id)
        if not current_user:
            raise ValueError("Không tìm thấy người dùng hiện tại.")
        
        # Kiểm tra xem đã là bạn bè chưa
        if target_user_id in current_user.friendIds:
            return 'friends'
        
        # Kiểm tra lời mời kết bạn
        # Lời mời do user_id gửi cho target_user_id
        sent_request = await FriendRequest.find_one({
            "fromUserId": user_id,
            "toUserId": target_user_id,
            "status": "pending"
        })
        if sent_request:
            return 'pending_sent'
        
        # Lời mời do target_user_id gửi cho user_id
        received_request = await FriendRequest.find_one({
            "fromUserId": target_user_id,
            "toUserId": user_id,
            "status": "pending"
        })
        if received_request:
            return 'pending_received'
        
        return 'none'

    @staticmethod
    async def unfriend_user(user_id: str, friend_id: str):
        """
        Hủy kết bạn với một người dùng.
        """
        if user_id == friend_id:
            raise ValueError("Không thể hủy kết bạn với chính mình.")
        
        # Lấy thông tin cả hai người dùng
        user = await User.get(user_id)
        friend = await User.get(friend_id)
        
        if not user or not friend:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Kiểm tra xem có phải bạn bè không
        if friend_id not in user.friendIds:
            raise ValueError("Người dùng này không phải là bạn bè của bạn.")
        
        # Xóa khỏi danh sách bạn bè của cả hai
        user.friendIds.remove(friend_id)
        friend.friendIds.remove(user_id)
        
        # Lưu thay đổi
        await user.save()
        await friend.save()
        
        return {"message": "Đã hủy kết bạn thành công."}

    @staticmethod
    async def update_user(user_id: str, user_update: UserUpdate):
        """
        Cập nhật thông tin người dùng, bao gồm cả upload avatar và background lên Cloudinary.
        """
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")

        update_data = user_update.model_dump(exclude_unset=True)

        tmp_avatar_path = None
        tmp_background_path = None

        try:
            if "avatarBase64" in update_data and update_data["avatarBase64"]:
                avatar_data = update_data["avatarBase64"]
                
                # Giải mã base64 với padding tự động
                if "," in avatar_data:
                    header, data = avatar_data.split(",", 1)
                    # Thêm padding nếu cần
                    missing_padding = len(data) % 4
                    if missing_padding:
                        data += "=" * (4 - missing_padding)
                    image_bytes = base64.b64decode(data, validate=True)
                else:
                    # Thêm padding nếu cần
                    data = avatar_data
                    missing_padding = len(data) % 4
                    if missing_padding:
                        data += "=" * (4 - missing_padding)
                    image_bytes = base64.b64decode(data, validate=True)

                # Lưu tạm file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(image_bytes)
                    tmp_avatar_path = tmp.name

                # Xóa ảnh cũ nếu có
                if user.avatarPublicId:
                    destroy(user.avatarPublicId)


                result = cloudinary_upload(tmp_avatar_path, folder="avatars")
                user.avatarUrl = result["secure_url"]
                user.avatarPublicId = result["public_id"]
                
                # Clean up temp file
                os.unlink(tmp_avatar_path)
                tmp_avatar_path = None

            # 2️⃣ Upload Background lên Cloudinary
            if "backgroundBase64" in update_data and update_data["backgroundBase64"]:
                background_data = update_data["backgroundBase64"]
                
                # Giải mã base64 với padding tự động
                if "," in background_data:
                    header, data = background_data.split(",", 1)
                    # Thêm padding nếu cần
                    missing_padding = len(data) % 4
                    if missing_padding:
                        data += "=" * (4 - missing_padding)
                    image_bytes = base64.b64decode(data, validate=True)
                else:
                    # Thêm padding nếu cần
                    data = background_data
                    missing_padding = len(data) % 4
                    if missing_padding:
                        data += "=" * (4 - missing_padding)
                    image_bytes = base64.b64decode(data, validate=True)

                # Lưu tạm file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(image_bytes)
                    tmp_background_path = tmp.name

                # Xóa ảnh cũ nếu có
                if user.backgroundPublicId:
                    destroy(user.backgroundPublicId)

                result = cloudinary_upload(tmp_background_path, folder="backgrounds")
                user.backgroundUrl = result["secure_url"]
                user.backgroundPublicId = result["public_id"]
                
                # Clean up temp file
                os.unlink(tmp_background_path)
                tmp_background_path = None

            # 3️⃣ Cập nhật các trường text
            if "displayName" in update_data and update_data["displayName"]:
                user.displayName = update_data["displayName"]
                
            if "bio" in update_data:
                user.bio = update_data["bio"] if update_data["bio"] else ""

            # 4️⃣ Lưu vào database
            await user.save()
            
            return user

        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # Clean up temp files on error
            if tmp_avatar_path and os.path.exists(tmp_avatar_path):
                try:
                    os.unlink(tmp_avatar_path)
                except:
                    pass
            if tmp_background_path and os.path.exists(tmp_background_path):
                try:
                    os.unlink(tmp_background_path)
                except:
                    pass
            
            raise ValueError(f"Lỗi cập nhật thông tin: {str(e)}")
    
    @staticmethod
    async def update_user_avatar(user_id: str, avatar_file: UploadFile):
        """Cập nhật avatar từ file upload."""
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Đọc file content
        file_content = await avatar_file.read()
        
        # Lưu tạm file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(file_content)
            tmp_avatar_path = tmp.name
        
        try:
            # Xóa ảnh cũ nếu có
            if user.avatarPublicId:
                destroy(user.avatarPublicId)
            
            # Upload lên Cloudinary
            result = cloudinary_upload(tmp_avatar_path, folder="avatars")
            user.avatarUrl = result["secure_url"]
            user.avatarPublicId = result["public_id"]
            
            await user.save()
            return user
        finally:
            # Clean up temp file
            if os.path.exists(tmp_avatar_path):
                os.unlink(tmp_avatar_path)
    
    @staticmethod
    async def update_user_background(user_id: str, background_file: UploadFile):
        """Cập nhật background từ file upload."""
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Đọc file content
        file_content = await background_file.read()
        
        # Lưu tạm file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(file_content)
            tmp_background_path = tmp.name
        
        try:
            # Xóa ảnh cũ nếu có
            if user.backgroundPublicId:
                destroy(user.backgroundPublicId)
            
            # Upload lên Cloudinary
            result = cloudinary_upload(tmp_background_path, folder="backgrounds")
            user.backgroundUrl = result["secure_url"]
            user.backgroundPublicId = result["public_id"]
            
            await user.save()
            return user
        finally:
            # Clean up temp file
            if os.path.exists(tmp_background_path):
                os.unlink(tmp_background_path)

    @staticmethod
    async def delete_account(user_id: str):
        """
        Xóa tài khoản người dùng (soft delete) bằng cách đổi status thành 'deleted'.
        Không xóa khỏi database.
        """
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Kiểm tra xem tài khoản đã bị xóa chưa
        if user.status == 'deleted':
            raise ValueError("Tài khoản này đã bị xóa trước đó.")
        
        # Đổi status thành deleted
        user.status = 'deleted'
        user.updatedAt = datetime.utcnow()
        await user.save()
        
        return {"message": "Tài khoản đã được xóa thành công."}

    @staticmethod
    async def get_blocked_users(user_id: str):
        """
        Lấy danh sách người dùng bị chặn bởi người dùng hiện tại.
        """
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")

        # Lấy danh sách người dùng bị chặn
        blocked_users = await User.find({"_id": {"$in": [ObjectId(uid) for uid in user.blockedUserIds]}}).to_list()
        return [
            {
                "id": str(blocked_user.id),
                "username": blocked_user.username,
                "displayName": blocked_user.displayName,
                "avatarUrl": blocked_user.avatarUrl
            }
            for blocked_user in blocked_users
        ]

    @staticmethod
    async def check_block_status(user_id: str, other_user_id: str):
        """
        Kiểm tra trạng thái block giữa hai người dùng.
        Returns: {"isBlockedByMe": bool, "isBlockedByOther": bool}
        """
        user = await User.get(user_id)
        other_user = await User.get(other_user_id)
        
        if not user or not other_user:
            raise ValueError("Không tìm thấy người dùng.")

        is_blocked_by_me = other_user_id in user.blockedUserIds
        is_blocked_by_other = user_id in other_user.blockedUserIds

        return {
            "isBlockedByMe": is_blocked_by_me,
            "isBlockedByOther": is_blocked_by_other,
            "isBlocked": is_blocked_by_me or is_blocked_by_other
        }