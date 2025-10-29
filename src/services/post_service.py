import asyncio
from typing import List
from cloudinary.uploader import destroy as cloudinary_destroy
from fastapi import UploadFile
from bson import ObjectId
from ..models import Post, AuthorInfo, Reaction, MediaItem, User
from ..websocket import manager
from ..schemas import PostPublic
from ..utils import upload_to_cloudinary

class PostService:

    @staticmethod
    async def create_post(author_id: str, content: str, files: List[UploadFile] = []):
        """
        Tạo một bài đăng mới.
        Upload ảnh/video (nếu có) lên Cloudinary, lưu URL và public_id.
        """
        author = await User.get(author_id)
        if not author:
            raise ValueError("Không tìm thấy tác giả.")

        author_info = AuthorInfo(
            displayName=author.displayName,
            avatarUrl=author.avatarUrl
        )

        uploaded_media = []  # Danh sách các MediaItem đã upload
        try:
            if files and len(files) > 0:
                # Upload tất cả files lên Cloudinary đồng thời
                upload_tasks = [upload_to_cloudinary(f, folder="posts") for f in files]
                results = await asyncio.gather(*upload_tasks)
                
                # Chuyển đổi kết quả thành MediaItem
                for result in results:
                    uploaded_media.append(
                        MediaItem(
                            url=result["url"],
                            publicId=result["public_id"],
                            type=result.get("resource_type", "image")
                        )
                    )

            # Tạo bài đăng mới
            new_post = Post(
                authorId=author_id,
                authorInfo=author_info,
                content=content,
                media=uploaded_media,
            )
            await new_post.save()

            # Tạo notification cho tất cả bạn bè (chạy nền không block)
            async def create_notifications_in_background():
                if author.friendIds:
                    from ..services.notification_service import NotificationService
                    # Create notification tasks
                    notification_tasks = [
                        NotificationService.create_notification(
                            user_id=friend_id,
                            notification_type="new_post",
                            title="Bài viết mới",
                            message=f"{author.displayName} đã đăng một bài viết mới",
                            metadata={
                                "authorId": str(author.id),
                                "authorDisplayName": author.displayName,
                                "authorAvatarUrl": author.avatarUrl,
                                "postId": str(new_post.id)
                            }
                        )
                        for friend_id in author.friendIds
                    ]
                    # Run all notifications
                    await asyncio.gather(*notification_tasks, return_exceptions=True)
            
            # Start notification task in background
            asyncio.create_task(create_notifications_in_background())

            # Gửi thông báo real-time
            notification_payload = {
                "type": "new_post",
                "payload": {
                    "authorId": str(author.id),
                    "authorName": author.displayName,
                    "postId": str(new_post.id)
                }
            }

            # Broadcast notification to all friends (chạy nền không block)
            async def broadcast_notifications_in_background():
                if author.friendIds:
                    for fid in author.friendIds:
                        try:
                            await manager.broadcast_to_user(fid, notification_payload)
                        except Exception as e:
                            print(f"Error broadcasting to user {fid}: {e}")
            
            # Start broadcast task in background
            asyncio.create_task(broadcast_notifications_in_background())

            return new_post

        except Exception as e:
            # Rollback: xóa media đã upload nếu có lỗi
            for media in uploaded_media:
                if media.publicId:
                    try:
                        cloudinary_destroy(media.publicId)
                    except:
                        pass
            raise ValueError(f"Lỗi khi tạo bài đăng: {e}")

    @staticmethod
    async def get_post_feed(user_id: str, limit: int = 20, skip: int = 0):
        """
        Lấy một nguồn cấp dữ liệu về các bài đăng từ bạn bè.
        Chỉ lấy posts từ những users chưa bị xóa (status != 'deleted') và là bạn bè.
        """
        # Lấy thông tin current user để lấy danh sách bạn bè
        current_user = await User.get(user_id)
        if not current_user:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Danh sách ID của bạn bè + chính mình
        friend_ids = [user_id] + current_user.friendIds
        
        # Truy vấn các bài đăng từ bạn bè
        posts = await Post.find(
            {
                "authorId": {"$in": friend_ids}
            },
            sort="-createdAt", 
            skip=skip, 
            limit=limit
        ).to_list()

        # Lấy danh sách author IDs
        author_ids = list(set(str(post.authorId) for post in posts))
        
        # Lấy thông tin các tác giả
        authors = await User.find({"_id": {"$in": [ObjectId(uid) for uid in author_ids]}}).to_list()
        
        # Tạo map để kiểm tra status
        author_status_map = {str(author.id): author.status for author in authors}
        
        # Lọc ra chỉ những posts từ users không bị xóa
        valid_posts = [
            post for post in posts 
            if author_status_map.get(str(post.authorId)) != 'deleted'
        ]

        return [ 
            PostPublic(
                id=str(post.id),
                authorId=str(post.authorId),
                authorInfo=post.authorInfo,
                content=post.content,
                mediaUrls=post.mediaUrls,
                reactions=post.reactions,
                reactionCounts=post.reactionCounts,
                createdAt=post.createdAt.isoformat()
            ) for post in valid_posts 
        ]

    @staticmethod
    async def get_user_posts(user_id: str, limit: int = 20, skip: int = 0):
        """
        Lấy danh sách các bài đăng của một người dùng cụ thể.
        """
        # Lấy thông tin user
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Chỉ lấy posts nếu user chưa bị xóa
        if user.status == 'deleted':
            raise ValueError("Tài khoản đã bị xóa.")
        
        # Truy vấn các bài đăng của user
        posts = await Post.find(
            {
                "authorId": user_id
            },
            sort="-createdAt", 
            skip=skip, 
            limit=limit
        ).to_list()

        return [ 
            PostPublic(
                id=str(post.id),
                authorId=str(post.authorId),
                authorInfo=post.authorInfo,
                content=post.content,
                mediaUrls=post.mediaUrls,
                reactions=post.reactions,
                reactionCounts=post.reactionCounts,
                createdAt=post.createdAt.isoformat()
            ) for post in posts 
        ]

    @staticmethod
    async def react_to_post(user_id: str, post_id: str, reaction_type: str):
        """
        Thêm hoặc thay đổi phản ứng của người dùng đối với một bài đăng.
        """
        post = await Post.get(post_id)
        if not post:
            raise ValueError("Không tìm thấy bài đăng.")
        
        # Lấy thông tin user đang react
        user = await User.get(user_id)
        if not user:
            raise ValueError("Không tìm thấy người dùng.")
        
        # Tìm phản ứng hiện có của người dùng
        existing_reaction_index = -1
        for i, reaction in enumerate(post.reactions):
            if reaction.userId == user_id:
                existing_reaction_index = i
                break

        is_new_reaction = existing_reaction_index == -1

        if existing_reaction_index != -1:
            # Nếu người dùng đã phản ứng
            old_reaction_type = post.reactions[existing_reaction_index].type
            if old_reaction_type == reaction_type:
                # Nếu loại phản ứng giống nhau → Unreact (xóa reaction)
                post.reactions.pop(existing_reaction_index)
                post.reactionCounts[reaction_type] -= 1
                if post.reactionCounts[reaction_type] == 0:
                    del post.reactionCounts[reaction_type]
                await post.save()
                return post
            
            # Giảm số lượng của phản ứng cũ
            post.reactionCounts[old_reaction_type] -= 1
            if post.reactionCounts[old_reaction_type] == 0:
                del post.reactionCounts[old_reaction_type]
            
            # Cập nhật phản ứng
            post.reactions[existing_reaction_index].type = reaction_type
            # Tăng số lượng của phản ứng mới
            post.reactionCounts[reaction_type] = post.reactionCounts.get(reaction_type, 0) + 1
        else:
            # Nếu người dùng chưa phản ứng, hãy thêm một phản ứng mới
            post.reactions.append(Reaction(userId=user_id, type=reaction_type))
            # Tăng số lượng của phản ứng mới
            post.reactionCounts[reaction_type] = post.reactionCounts.get(reaction_type, 0) + 1
        
        # Lưu bài đăng đã cập nhật
        await post.save()
        
        # Tạo notification và broadcast WebSocket nếu có người mới thả reaction
        if is_new_reaction and post.authorId != user_id:
            # Lấy thông tin tác giả bài viết
            author = await User.get(post.authorId)
            if author and author.status != 'deleted':
                # Import here to avoid circular import
                from ..services.notification_service import NotificationService
                
                # Create notification in background
                async def create_reaction_notification():
                    await NotificationService.create_notification(
                        user_id=post.authorId,
                        notification_type="post_reaction",
                        title="Có người thích bài viết của bạn",
                        message=f"{user.displayName} đã thích bài viết của bạn",
                        metadata={
                            "userId": str(user.id),
                            "userDisplayName": user.displayName,
                            "userAvatarUrl": user.avatarUrl,
                            "postId": post_id,
                            "reactionType": reaction_type
                        }
                    )
                    
                    # Broadcast via WebSocket
                    notification_payload = {
                        "type": "post_reaction",
                        "payload": {
                            "userId": str(user.id),
                            "userDisplayName": user.displayName,
                            "userAvatarUrl": user.avatarUrl,
                            "postId": post_id,
                            "reactionType": reaction_type
                        }
                    }
                    await manager.broadcast_to_user(post.authorId, notification_payload)
                
                # Start notification task in background
                asyncio.create_task(create_reaction_notification())
        
        return post

    @staticmethod
    async def update_post(post_id: str, user_id: str, content: str, existing_image_urls: List[str], files: List):
        """
        Cập nhật bài đăng: nội dung, xóa ảnh cũ, giữ ảnh còn lại, thêm ảnh mới.
        """
        # Lấy bài đăng
        post = await Post.get(post_id)
        if not post:
            raise ValueError("Không tìm thấy bài đăng.")

        # Kiểm tra quyền
        if post.authorId != user_id:
            raise PermissionError("Bạn không được phép chỉnh sửa bài đăng này.")

        # Xác định ảnh nào bị xóa
        current_urls = {item.url for item in post.media}
        kept_urls = set(existing_image_urls)
        removed_urls = current_urls - kept_urls
        
        # Xóa ảnh bị removed khỏi Cloudinary
        new_media_list = []
        for media_item in post.media:
            if media_item.url in removed_urls:
                # Xóa khỏi Cloudinary
                try:
                    cloudinary_destroy(media_item.publicId)
                except Exception as e:
                    print(f"Failed to delete from Cloudinary: {e}")
            else:
                # Giữ lại ảnh
                new_media_list.append(media_item)
        
        # Upload ảnh mới
        if files:
            for file in files:
                try:
                    upload_result = await upload_to_cloudinary(file)
                    new_media_list.append(
                        MediaItem(
                            url=upload_result['url'],
                            publicId=upload_result['public_id'],
                            type='image'
                        )
                    )
                except Exception as e:
                    print(f"Failed to upload new image: {e}")
        
        # Cập nhật post
        post.content = content
        post.media = new_media_list
        await post.save()
        
        return post

    @staticmethod
    async def delete_post(post_id: str, user_id: str):
        """
        Xóa một bài đăng, đảm bảo người dùng là tác giả.
        """
        # Lấy bài đăng
        post = await Post.get(post_id)
        if not post:
            raise ValueError("Không tìm thấy bài đăng.")

        # Kiểm tra quyền
        if post.authorId != user_id:
            raise PermissionError("Bạn không được phép xóa bài đăng này.")

        # Xóa bài đăng
        await post.delete()
        return {"message": "Bài đăng đã được xóa thành công"}