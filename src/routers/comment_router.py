from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List
from ..services import CommentService
from ..schemas import CommentPublic, CommentCreate
from ..models import User
from ..security import get_current_user

router = APIRouter(tags=["Comment"])

@router.post("/posts/{post_id}/comments", response_model=CommentPublic, status_code=201)
async def create_comment(
    post_id: str,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user)
):
    """Tạo một bình luận mới cho bài đăng. Yêu cầu xác thực người dùng."""
    try:
        new_comment = await CommentService.create_comment(
            post_id=post_id,
            author_id=str(current_user.id),
            content=comment_data.content
        )
        return CommentPublic(
            id=str(new_comment.id),
            postId=str(new_comment.postId),
            authorId=str(new_comment.authorId),
            authorInfo=new_comment.authorInfo,
            content=new_comment.content,
            createdAt=new_comment.createdAt.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi server: {str(e)}")

@router.get("/posts/{post_id}/comments", response_model=List[CommentPublic])
async def get_comments(
    post_id: str,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách bình luận của một bài đăng."""
    try:
        comments = await CommentService.get_comments_by_post(
            post_id=post_id,
            skip=skip,
            limit=limit
        )
        return comments
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi server: {str(e)}")

@router.get("/posts/{post_id}/comments/count")
async def get_comment_count(
    post_id: str,
    current_user: User = Depends(get_current_user)
):
    """Lấy tổng số bình luận của một bài đăng."""
    try:
        count = await CommentService.get_comment_count(post_id)
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi server: {str(e)}")

@router.delete("/comments/{comment_id}", status_code=200)
async def delete_comment(
    comment_id: str,
    current_user: User = Depends(get_current_user)
):
    """Xóa một bình luận. Chỉ tác giả bình luận hoặc tác giả bài đăng mới có quyền xóa."""
    try:
        result = await CommentService.delete_comment(
            comment_id=comment_id,
            user_id=str(current_user.id)
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.put("/comments/{comment_id}", response_model=CommentPublic)
async def update_comment(
    comment_id: str,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user)
):
    """Cập nhật bình luận. Chỉ tác giả bình luận mới có quyền chỉnh sửa."""
    try:
        updated_comment = await CommentService.update_comment(
            comment_id=comment_id,
            user_id=str(current_user.id),
            content=comment_data.content
        )
        return CommentPublic(
            id=str(updated_comment.id),
            postId=str(updated_comment.postId),
            authorId=str(updated_comment.authorId),
            authorInfo=updated_comment.authorInfo,
            content=updated_comment.content,
            createdAt=updated_comment.createdAt.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

