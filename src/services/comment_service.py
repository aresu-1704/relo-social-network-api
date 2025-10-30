import asyncio
from typing import List
from bson import ObjectId
from ..models import Comment, AuthorInfo, User, Post
from ..schemas import CommentPublic
from ..websocket import manager

class CommentService:

    @staticmethod
    async def create_comment(post_id: str, author_id: str, content: str):
        """
        Tạo một bình luận mới cho bài đăng.
        """
        # Kiểm tra bài đăng có tồn tại không
        post = await Post.get(post_id)
        if not post:
            raise ValueError("Không tìm thấy bài đăng.")

        # Lấy thông tin tác giả bình luận
        author = await User.get(author_id)
        if not author:
            raise ValueError("Không tìm thấy người dùng.")

        # Kiểm tra user chưa bị xóa
        if author.status == 'deleted':
            raise ValueError("Tài khoản đã bị xóa.")

        author_info = AuthorInfo(
            displayName=author.displayName,
            avatarUrl=author.avatarUrl
        )

        # Tạo bình luận mới
        new_comment = Comment(
            postId=post_id,
            authorId=author_id,
            authorInfo=author_info,
            content=content.strip()
        )
        await new_comment.save()

        # Tạo notification cho tác giả bài đăng (nếu không phải chính mình)
        if post.authorId != author_id:
            async def create_comment_notification():
                from ..services.notification_service import NotificationService
                
                await NotificationService.create_notification(
                    user_id=post.authorId,
                    notification_type="post_comment",
                    title="Có người bình luận bài viết của bạn",
                    message=f"{author.displayName} đã bình luận: {content[:50]}...",
                    metadata={
                        "userId": str(author.id),
                        "userDisplayName": author.displayName,
                        "userAvatarUrl": author.avatarUrl,
                        "postId": post_id,
                        "commentId": str(new_comment.id)
                    }
                )
                
                # Broadcast via WebSocket
                notification_payload = {
                    "type": "post_comment",
                    "payload": {
                        "userId": str(author.id),
                        "userDisplayName": author.displayName,
                        "userAvatarUrl": author.avatarUrl,
                        "postId": post_id,
                        "commentId": str(new_comment.id)
                    }
                }
                await manager.broadcast_to_user(post.authorId, notification_payload)
            
            # Start notification task in background
            asyncio.create_task(create_comment_notification())

        return new_comment

    @staticmethod
    async def get_comments_by_post(post_id: str, skip: int = 0, limit: int = 50):
        """
        Lấy danh sách bình luận của một bài đăng, sắp xếp theo thời gian tạo (mới nhất trước).
        """
        comments = await Comment.find(
            {"postId": post_id},
            sort="-createdAt",
            skip=skip,
            limit=limit
        ).to_list()

        return [
            CommentPublic(
                id=str(comment.id),
                postId=str(comment.postId),
                authorId=str(comment.authorId),
                authorInfo=comment.authorInfo,
                content=comment.content,
                createdAt=comment.createdAt.isoformat()
            ) for comment in comments
        ]

    @staticmethod
    async def get_comment_count(post_id: str) -> int:
        """
        Lấy tổng số bình luận của một bài đăng.
        """
        count = await Comment.find({"postId": post_id}).count()
        return count

    @staticmethod
    async def delete_comment(comment_id: str, user_id: str):
        """
        Xóa một bình luận. Chỉ tác giả bình luận hoặc tác giả bài đăng mới có quyền xóa.
        """
        comment = await Comment.get(comment_id)
        if not comment:
            raise ValueError("Không tìm thấy bình luận.")

        # Lấy thông tin bài đăng
        post = await Post.get(comment.postId)
        if not post:
            raise ValueError("Không tìm thấy bài đăng.")

        # Kiểm tra quyền: chỉ tác giả bình luận hoặc tác giả bài đăng mới được xóa
        if comment.authorId != user_id and post.authorId != user_id:
            raise PermissionError("Bạn không được phép xóa bình luận này.")

        await comment.delete()
        return {"message": "Bình luận đã được xóa thành công"}

    @staticmethod
    async def update_comment(comment_id: str, user_id: str, content: str):
        """
        Cập nhật bình luận. Chỉ tác giả bình luận mới có quyền chỉnh sửa.
        """
        comment = await Comment.get(comment_id)
        if not comment:
            raise ValueError("Không tìm thấy bình luận.")

        # Kiểm tra quyền
        if comment.authorId != user_id:
            raise PermissionError("Bạn không được phép chỉnh sửa bình luận này.")

        comment.content = content.strip()
        await comment.save()
        
        return comment

