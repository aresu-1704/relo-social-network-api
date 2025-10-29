from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Body
from typing import List, Optional
from ..services import PostService
from ..schemas import PostPublic, ReactionCreate
from ..models import User
from ..security import get_current_user

router = APIRouter(tags=["Post"])

@router.post("", response_model=PostPublic, status_code=201)
async def create_post(
    current_user: User = Depends(get_current_user),
    content: str = Form(""),
    files: List[UploadFile] = File(default=[])
):
    """Tạo một bài đăng mới. Yêu cầu xác thực người dùng."""
    try:
        
        # Validate: cần ít nhất content hoặc files
        has_content = content and content.strip()
        has_files = len(files) > 0
        
        if not has_content and not has_files:
            raise ValueError('Vui lòng nhập nội dung hoặc chọn ảnh')
        
        # Gọi service để tạo bài đăng một cách bất đồng bộ
        new_post = await PostService.create_post(
            author_id=str(current_user.id),
            content=content,
            files=files
        )
        # Ánh xạ kết quả trả về sang schema PostPublic
        return PostPublic(
            id=str(new_post.id),
            authorId=str(new_post.authorId),
            authorInfo=new_post.authorInfo,
            content=new_post.content,
            mediaUrls=new_post.mediaUrls,
            reactions=new_post.reactions,
            reactionCounts=new_post.reactionCounts,
            createdAt=new_post.createdAt.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Lỗi validation: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi server: {str(e)}")

@router.get("/feed", response_model=List[PostPublic])
async def get_post_feed(
    skip: int = 0, 
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Lấy một nguồn cấp dữ liệu (feed) các bài đăng của bạn bè."""
    # Lấy danh sách bài đăng một cách bất đồng bộ
    posts = await PostService.get_post_feed(
        user_id=str(current_user.id),
        limit=limit, 
        skip=skip
    )
    # Ánh xạ danh sách kết quả sang schema PostPublic
    return posts

@router.get("/user/{user_id}", response_model=List[PostPublic])
async def get_user_posts(
    user_id: str,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách các bài đăng của một người dùng cụ thể."""
    try:
        posts = await PostService.get_user_posts(user_id, limit=limit, skip=skip)
        return posts
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{post_id}/react", response_model=PostPublic)
async def react_to_post(
    post_id: str,
    reaction_data: ReactionCreate,
    current_user: User = Depends(get_current_user)
):
    """Thêm hoặc thay đổi một phản ứng (reaction) cho một bài đăng. Yêu cầu xác thực."""
    try:
        # Gọi service để cập nhật phản ứng một cách bất đồng bộ
        updated_post = await PostService.react_to_post(
            user_id=str(current_user.id),
            post_id=post_id,
            reaction_type=reaction_data.reaction_type
        )
        # Ánh xạ kết quả trả về sang schema PostPublic
        return PostPublic(
            id=str(updated_post.id),
            authorId=str(updated_post.authorId),
            authorInfo=updated_post.authorInfo,
            content=updated_post.content,
            mediaUrls=updated_post.mediaUrls,
            reactions=updated_post.reactions,
            reactionCounts=updated_post.reactionCounts,
            createdAt=updated_post.createdAt.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/{post_id}", response_model=PostPublic)
async def update_post(
    post_id: str,
    content: str = Form(...),
    existing_image_urls: Optional[List[str]] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    current_user: User = Depends(get_current_user)
):
    """Cập nhật bài đăng. Chỉ tác giả mới có quyền chỉnh sửa."""
    try:
        # Gọi service để cập nhật bài đăng
        updated_post = await PostService.update_post(
            post_id=post_id,
            user_id=str(current_user.id),
            content=content,
            existing_image_urls=existing_image_urls or [],
            files=files or []
        )
        
        # Ánh xạ kết quả trả về sang schema PostPublic
        return PostPublic(
            id=str(updated_post.id),
            authorId=str(updated_post.authorId),
            authorInfo=updated_post.authorInfo,
            content=updated_post.content,
            mediaUrls=updated_post.mediaUrls,
            reactions=updated_post.reactions,
            reactionCounts=updated_post.reactionCounts,
            createdAt=updated_post.createdAt.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.delete("/{post_id}", status_code=200)
async def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user)
):
    """Xóa một bài đăng. Chỉ tác giả của bài đăng mới có quyền xóa."""
    try:
        # Gọi service để xóa bài đăng một cách bất đồng bộ
        result = await PostService.delete_post(post_id=post_id, user_id=str(current_user.id))
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))